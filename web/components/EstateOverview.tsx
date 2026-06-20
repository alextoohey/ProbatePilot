import type { EstateState } from "@/types/estate";

export function EstateOverview({ estate }: { estate: EstateState }) {
  const assetTotal = estate.assets.reduce((sum, asset) => sum + (asset.estimatedValue ?? 0), 0);
  const debtTotal = estate.debts.reduce((sum, debt) => sum + debt.amount, 0);

  return (
    <section className="grid gap-4 md:grid-cols-4">
      <div>
        <p className="text-sm text-slate-600">Estate</p>
        <p className="font-semibold">{estate.deceasedName}</p>
      </div>
      <div>
        <p className="text-sm text-slate-600">Executor</p>
        <p className="font-semibold">{estate.executor.name}</p>
      </div>
      <div>
        <p className="text-sm text-slate-600">Assets</p>
        <p className="font-semibold">${assetTotal.toLocaleString()}</p>
      </div>
      <div>
        <p className="text-sm text-slate-600">Debts</p>
        <p className="font-semibold">${debtTotal.toLocaleString()}</p>
      </div>
    </section>
  );
}

