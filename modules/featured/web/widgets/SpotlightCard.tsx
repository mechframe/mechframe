// The Dashboard's "Now in the spotlight" (`dev plans/contracts/featured.md` §2; VM
// Website `AdminDashboard.dc.html`): a card for each player marked to show there,
// with what plays first, since when and how many more are queued, or "Nothing"
// while it's empty on the site, and a link to its tab on Players.
import { LoadError, StatCard, type StatCardProps } from "@/kernel";

import { SLOTS, liveLine, useApiQuery, type AdminSlot } from "../api";

/** A player's card words. */
export function cardOf(slot: AdminSlot): StatCardProps {
  const label = `Now in the ${slot.label.toLowerCase()}`;
  const link = { label: "Players", to: `/admin/featured?slot=${encodeURIComponent(slot.key)}` };
  if (!slot.now) return { label, value: "Nothing", line: `The ${slot.label} is empty on the site`, state: { tone: "warning", label: "Not live" }, link };
  return { label, value: slot.now.title, line: liveLine(slot), state: { tone: "success", label: "Live" }, link };
}

export default function SpotlightCard() {
  const listed = useApiQuery("get", SLOTS);
  if (listed.error) return <LoadError what="The players" error={listed.error} onRetry={() => void listed.refetch()} />;
  if (!listed.data) return <StatCard label="Now in the spotlight" value="…" line="Reading the players…" />;
  return (
    <>
      {listed.data.items
        .filter((slot) => slot.on_dashboard)
        .map((slot) => (
          <StatCard key={slot.key} {...cardOf(slot)} />
        ))}
    </>
  );
}
