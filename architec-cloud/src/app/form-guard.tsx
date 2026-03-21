"use client";

import { useEffect } from "react";

export default function FormGuard() {
  useEffect(() => {
    function handleSubmit(event: Event) {
      const target = event.target;
      if (!(target instanceof HTMLFormElement)) {
        return;
      }

      const message = target.dataset.confirmMessage?.trim();
      if (message && !window.confirm(message)) {
        event.preventDefault();
        return;
      }

      const activeElement = document.activeElement;
      if (!(activeElement instanceof HTMLButtonElement) || activeElement.form !== target) {
        return;
      }

      const busyLabel = activeElement.dataset.busyLabel?.trim();
      if (!busyLabel) {
        return;
      }

      activeElement.dataset.originalLabel = activeElement.textContent || "";
      activeElement.textContent = busyLabel;
      activeElement.disabled = true;
    }

    window.addEventListener("submit", handleSubmit, true);
    return () => window.removeEventListener("submit", handleSubmit, true);
  }, []);

  return null;
}
