"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Label, PageHeader, PasswordInput, toast } from "@/components/ui";
import { TelegramLink } from "@/components/telegram-link";
import { DeliverySettings } from "@/components/delivery-settings";

export default function AccountPage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const changeMutation = useMutation({
    mutationFn: () =>
      api.post("/account/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: () => {
      toast.success("Passwort erfolgreich geändert.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Passwort konnte nicht geändert werden."),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirm) {
      toast.error("Die Passwörter stimmen nicht überein.");
      return;
    }
    changeMutation.mutate();
  };

  return (
    <div>
      <PageHeader title="Mein Konto" description={user?.email} />

      <div className="mt-6 max-w-md space-y-6">
        <Card className="p-6">
          <h2 className="font-semibold text-foreground">Passwort ändern</h2>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div>
              <Label htmlFor="current-password">Aktuelles Passwort</Label>
              <PasswordInput
                id="current-password"
                className="mt-1"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <div>
              <Label htmlFor="new-password">Neues Passwort</Label>
              <PasswordInput
                id="new-password"
                className="mt-1"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <div>
              <Label htmlFor="confirm-password">Neues Passwort bestätigen</Label>
              <PasswordInput
                id="confirm-password"
                className="mt-1"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" disabled={changeMutation.isPending} className="w-full">
              {changeMutation.isPending ? "Speichern…" : "Passwort ändern"}
            </Button>
          </form>
        </Card>

        <DeliverySettings />

        <TelegramLink />
      </div>
    </div>
  );
}
