"use client";

import { useEffect, useState } from "react";

type Props = {
  nextUrl: string;
};

export default function ContinueToTarget({ nextUrl }: Props) {
  const [secondsLeft, setSecondsLeft] = useState(2);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setSecondsLeft((value) => (value > 1 ? value - 1 : 1));
    }, 1000);
    const timeout = window.setTimeout(() => {
      window.location.replace(nextUrl);
    }, 1600);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [nextUrl]);

  return (
    <p className="muted">
      Redirecting to the waiting CLI callback in about {secondsLeft} second{secondsLeft === 1 ? "" : "s"}.
      If nothing happens, use the manual continue link below.
    </p>
  );
}
