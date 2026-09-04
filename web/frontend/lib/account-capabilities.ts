import type { User } from "./types";

type Account = User | null | undefined;
type ModerationOnlyAccount = User & { role: "moderator" };
type ReportReviewerAccount = User & { role: "admin" | "moderator" };

/** A moderator has one deliberately narrow workspace, unlike an administrator. */
export function isModerationOnly(account: Account): account is ModerationOnlyAccount {
  return account?.role === "moderator";
}

/** Human report decisions are available to administrators and moderators. */
export function canModerateReports(account: Account): account is ReportReviewerAccount {
  return account?.status === "active" && (
    account.role === "admin"
    || (isModerationOnly(account) && account.email_verified)
  );
}
