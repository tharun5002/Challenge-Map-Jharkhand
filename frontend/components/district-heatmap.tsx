import type { DistrictStat } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

/**
 * Schematic district intensity grid.
 *
 * Deliberately not a geographic map: the project does not yet ship a verified
 * 24-district boundary file, and inventing one would misrepresent geography.
 * The label says so. Phase 6 replaces this with a react-leaflet choropleth once
 * data/geography/jharkhand_districts.geojson is validated.
 */
export function DistrictHeatmap({ districts }: { districts: DistrictStat[] }) {
  const max = Math.max(...districts.map((district) => district.complaints));

  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {districts.map((district) => {
          const intensity = district.complaints / max;
          return (
            <div
              key={district.name}
              className="group relative overflow-hidden rounded-xl border border-line p-3 transition hover:border-teal/40"
              style={{ backgroundColor: `rgba(15, 118, 110, ${0.06 + intensity * 0.42})` }}
              title={`${district.name}: ${formatNumber(district.complaints)} complaints`}
            >
              <p className="truncate text-[11px] font-semibold leading-tight text-fg">
                {district.name}
              </p>
              <p className="mt-1 text-lg font-extrabold leading-none tracking-tight text-fg">
                {formatNumber(district.complaints)}
              </p>
              <p className="mt-1 text-[10px] text-fg-soft">
                {formatNumber(district.critical)} critical
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-[11px] text-fg-subtle">
        <div className="flex items-center gap-2">
          <span>Fewer</span>
          <span className="h-2 w-24 rounded-full bg-gradient-to-r from-teal/10 to-teal/60" />
          <span>More reports</span>
        </div>
        <span>Schematic layout — verified district boundaries pending (Phase 6)</span>
      </div>
    </div>
  );
}
