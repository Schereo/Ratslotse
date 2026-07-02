"use client";

import { PageHeader } from "@/components/ui";
import { TelegramLink } from "@/components/telegram-link";

export default function LinkPage() {
  return (
    <div>
      <PageHeader title="Telegram verbinden" description="Verknüpfe dein Web-Konto mit dem Telegram-Bot." />
      <div className="mt-6 max-w-md">
        <TelegramLink />
      </div>
    </div>
  );
}
