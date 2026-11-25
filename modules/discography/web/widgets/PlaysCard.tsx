// The Dashboard's "Plays this week" (`dev plans/contracts/audio-player.md` §2,
// "discography 0.1.1"; VM Website `AdminDashboard.dc.html`): the last seven days'
// plays, the change on the seven before ("Up 18% on last week"), the track that
// leads, and a link to Music. A card for those who manage the library.
import { LoadError, StatCard, type StatCardProps } from "@/kernel";

import { PLAYS, useApiQuery, type PlaysWeek } from "../api";

/** The card's figure, its line and its pill, from the week's answer. */
export function playsWords(week: PlaysWeek): Pick<StatCardProps, "value" | "line" | "state"> {
  const value = week.this_week.toLocaleString("en-US");
  if (week.this_week === 0) return { value, line: "No plays yet this week" };
  const leads = week.leading ? `; ${week.leading} leads` : "";
  if (week.last_week === 0) return { value, line: `None the week before${leads}`, state: { tone: "info", label: "New" } };
  const change = Math.round(((week.this_week - week.last_week) / week.last_week) * 100);
  if (change > 0) return { value, line: `Up ${String(change)}% on last week${leads}`, state: { tone: "success", label: `Up ${String(change)}%` } };
  if (change < 0) return { value, line: `Down ${String(-change)}% on last week${leads}`, state: { tone: "warning", label: `Down ${String(-change)}%` } };
  return { value, line: `The same as last week${leads}`, state: { tone: "neutral", label: "Level" } };
}

export default function PlaysCard() {
  const week = useApiQuery("get", PLAYS);
  if (week.error) return <LoadError what="Plays this week" error={week.error} onRetry={() => void week.refetch()} />;
  if (!week.data) return <StatCard label="Plays this week" value="…" line="Counting the plays…" />;
  return <StatCard label="Plays this week" {...playsWords(week.data)} link={{ label: "Music", to: "/admin/music" }} />;
}
