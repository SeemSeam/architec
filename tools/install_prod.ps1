#Requires -Version 5.1

[CmdletBinding()]
param(
    [string]$Version,
    [string]$Repo,
    [string]$BaseUrl,
    [string]$InstallBase,
    [string]$BinDir,
    [string]$Arch,
    [string]$AssetName,
    [switch]$SkipChecksum,
    [switch]$ConfigureLLM,
    [switch]$SkipLLMConfig
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-EnvOrDefault {
    param([string]$Name, [string]$DefaultValue = "")
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $DefaultValue }
    return $value.Trim()
}

function Normalize-Arch {
    param([string]$Value)
    $raw = ""
    if ($null -ne $Value) {
        $raw = $Value.Trim().ToLowerInvariant()
    }
    switch ($raw) {
        "amd64" { return "x64" }
        "x86_64" { return "x64" }
        "x64" { return "x64" }
        "arm64" { return "arm64" }
        "aarch64" { return "arm64" }
        default { throw "Unsupported CPU architecture: $Value" }
    }
}

function Normalize-Version {
    param([string]$Value)
    if ($Value.StartsWith("v")) { return $Value.Substring(1) }
    return $Value
}

function Resolve-Version {
    param([string]$TargetRepo, [string]$Selector)
    if (-not [string]::IsNullOrWhiteSpace($Selector) -and $Selector -ne "latest") {
        return Normalize-Version -Value $Selector
    }
    $metadata = Invoke-RestMethod -Headers @{ "User-Agent" = "architec-installer" } `
        -Uri "https://api.github.com/repos/$TargetRepo/releases/latest"
    if ([string]::IsNullOrWhiteSpace($metadata.tag_name)) {
        throw "latest GitHub Release metadata did not contain tag_name"
    }
    return Normalize-Version -Value ([string]$metadata.tag_name)
}

function Asset-NameFor {
    param([string]$TargetVersion, [string]$Triplet)
    return "archi-v$TargetVersion-$Triplet.exe"
}

function Checksum-NameFor {
    param([string]$TargetVersion)
    return "archi-v$TargetVersion-checksums.txt"
}

function Download-File {
    param([string]$Url, [string]$OutputPath)
    if ($Url.StartsWith("file://")) {
        $localPath = [System.Uri]$Url
        Copy-Item -Path $localPath.LocalPath -Destination $OutputPath -Force
        return
    }
    Invoke-WebRequest -Uri $Url -OutFile $OutputPath -UseBasicParsing
}

function Verify-Checksum {
    param([string]$BinaryPath, [string]$ChecksumsPath, [string]$ExpectedName)
    $expected = ""
    foreach ($line in Get-Content -Path $ChecksumsPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $parts = $trimmed -split "\s+"
        if ($parts.Length -ge 2 -and $parts[-1].TrimStart("*") -eq $ExpectedName) {
            $expected = $parts[0].ToLowerInvariant()
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($expected)) {
        throw "checksum entry not found for $ExpectedName"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -Path $BinaryPath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "checksum mismatch for $ExpectedName`: expected $expected, got $actual"
    }
}

function Write-TextFileIfMissing {
    param([string]$PathValue, [string]$Content)
    if (Test-Path $PathValue) { return $false }
    $parent = Split-Path -Parent $PathValue
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $PathValue -Value $Content -Encoding UTF8
    return $true
}

$Repo = if ($PSBoundParameters.ContainsKey("Repo")) { $Repo } else { Get-EnvOrDefault -Name "ARCHITEC_RELEASE_REPO" -DefaultValue "SeemSeam/architec" }
$Version = if ($PSBoundParameters.ContainsKey("Version")) { $Version } else { Get-EnvOrDefault -Name "ARCHITEC_VERSION" -DefaultValue "latest" }
$BaseUrl = if ($PSBoundParameters.ContainsKey("BaseUrl")) { $BaseUrl.TrimEnd("/") } else { (Get-EnvOrDefault -Name "ARCHITEC_DOWNLOAD_BASE_URL").TrimEnd("/") }
$InstallBase = if ($PSBoundParameters.ContainsKey("InstallBase")) { $InstallBase } else { Get-EnvOrDefault -Name "ARCHITEC_INSTALL_BASE" -DefaultValue (Join-Path $env:LOCALAPPDATA "Architec") }
$BinDir = if ($PSBoundParameters.ContainsKey("BinDir")) { $BinDir } else { Get-EnvOrDefault -Name "ARCHITEC_BIN_DIR" -DefaultValue (Join-Path $InstallBase "bin") }
$archOverride = Get-EnvOrDefault -Name "ARCHITEC_TARGET_ARCH"
$archRaw = if ($PSBoundParameters.ContainsKey("Arch")) {
    $Arch
} elseif (-not [string]::IsNullOrWhiteSpace($archOverride)) {
    $archOverride
} else {
    ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture).ToString()
}
$Arch = Normalize-Arch -Value $archRaw
$VerifyChecksums = -not $SkipChecksum.IsPresent -and (Get-EnvOrDefault -Name "ARCHITEC_VERIFY_CHECKSUMS" -DefaultValue "1") -ne "0"

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $Version = Resolve-Version -TargetRepo $Repo -Selector $Version
    $BaseUrl = "https://github.com/$Repo/releases/download/v$Version"
} else {
    $Version = Normalize-Version -Value $Version
    if ([string]::IsNullOrWhiteSpace($Version) -or $Version -eq "latest") {
        throw "-Version is required when -BaseUrl is used"
    }
}

$triplet = "win32-$Arch"
$AssetName = if ($PSBoundParameters.ContainsKey("AssetName")) { $AssetName } else { Asset-NameFor -TargetVersion $Version -Triplet $triplet }
$checksumsName = Checksum-NameFor -TargetVersion $Version

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("architec-install-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    $binaryDownload = Join-Path $tempDir $AssetName
    $checksumsPath = Join-Path $tempDir $checksumsName
    Write-Host "Installing Architec $Version from GitHub Release assets"
    Download-File -Url "$BaseUrl/$AssetName" -OutputPath $binaryDownload
    if ($VerifyChecksums) {
        Download-File -Url "$BaseUrl/$checksumsName" -OutputPath $checksumsPath
        Verify-Checksum -BinaryPath $binaryDownload -ChecksumsPath $checksumsPath -ExpectedName $AssetName
        Write-Host "Checksum verification passed"
    }

    $targetDir = Join-Path $InstallBase $triplet
    if (Test-Path $targetDir) { Remove-Item -Recurse -Force $targetDir }
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    $targetBinary = Join-Path $targetDir "archi.exe"
    Copy-Item -Path $binaryDownload -Destination $targetBinary -Force
    Copy-Item -Path $targetBinary -Destination (Join-Path $BinDir "archi.exe") -Force

    $stateDir = Get-EnvOrDefault -Name "ARCHITEC_USER_CONFIG_DIR" -DefaultValue (Join-Path $HOME ".architec")
    $llmConfigPath = Get-EnvOrDefault -Name "ARCHITEC_LLM_CONFIG" -DefaultValue (Join-Path $stateDir "config.yaml")
    $gatewayConfigPath = Get-EnvOrDefault -Name "LLMGATEWAY_CONFIG" -DefaultValue (Join-Path (Get-EnvOrDefault -Name "LLMGATEWAY_USER_CONFIG_DIR" -DefaultValue (Join-Path $HOME ".llmgateway")) "config.yaml")
    $hippocampusConfigPath = Get-EnvOrDefault -Name "HIPPOCAMPUS_LLM_CONFIG" -DefaultValue (Join-Path (Get-EnvOrDefault -Name "HIPPOCAMPUS_USER_CONFIG_DIR" -DefaultValue (Join-Path $HOME ".hippocampus")) "config.yaml")

    Write-TextFileIfMissing -PathValue $llmConfigPath -Content @"
version: 1
tasks:
  architect_history:
    tier: strong
  architec_summary:
    tier: strong
"@ | Out-Null

    Write-TextFileIfMissing -PathValue $hippocampusConfigPath -Content @"
version: 1
tasks:
  architect:
    tier: strong
"@ | Out-Null

    $gatewayCreated = Write-TextFileIfMissing -PathValue $gatewayConfigPath -Content @"
# llmgateway config for Architec
# Created only when missing; install/update never overwrites existing credentials.
version: 1

providers:
  - provider_type: "openai"
    api_style: "openai_chat"
    base_url: ""
    api_key: ""
    headers: {}
    model_map: {}

  # Optional fallback provider example.
  # - provider_type: openai
  #   api_style: openai_chat
  #   base_url: `${ARCHITEC_LLM_SECONDARY_BASE_URL}
  #   api_key: `${ARCHITEC_LLM_SECONDARY_API_KEY}
  #   headers: {}
  #   model_map:
  #     gpt-5.4: secondary-provider-strong-model

settings:
  fallback_model: "gpt-5.4-mini"
  strong_model: "gpt-5.4"
  weak_model: "gpt-5.4-mini"
  strong_reasoning_effort: "high"
  weak_reasoning_effort: "low"
  max_concurrent: 4
  retry_max: 2
  transport_retries: 2
  timeout: 120
"@
    if ($gatewayCreated) {
        Write-Warning "Created a starter llmgateway config template at $gatewayConfigPath."
    } else {
        Write-Host "Keeping existing llmgateway config at $gatewayConfigPath"
    }

    Write-Host "Installed Architec $Version to $targetDir"
    Write-Host "Installed launcher $(Join-Path $BinDir 'archi.exe')"
} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Recurse -Force $tempDir
    }
}
