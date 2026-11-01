import { Skeleton, Stat } from "../ui";
import { money, signed, tone } from "./fmt";

/** Las tres cuentas en una fila de cifras grandes. */
function Summary({ board }) {
    const b = board?.balances;
    if (!b) {
        return (
            <div className="ui-stats">
                {[0, 1, 2].map((i) => (
                    <div key={i} className="ui-stat"><Skeleton lines={2} height={16} /></div>
                ))}
            </div>
        );
    }
    const pct = (bal, ini) => (ini ? ((bal - ini) / ini) * 100 : 0);
    const items = [];
    if (b.main) items.push(["Cuenta principal", b.main.balance, b.main.initial, b.main.open_positions ? `${b.main.open_positions} posiciones` : "En USDT, esperando tendencia"]);
    if (b.copier) items.push(["Copia de ganadoras", b.copier.balance, b.copier.initial, b.copier.copies?.length ? `Copia a ${b.copier.copies.join(", ")}` : "Sin ganadoras aún"]);
    items.push([`Torneo · ${b.tournament.accounts} estrategias`, b.tournament.balance, b.tournament.initial, `Cerradas ${signed(b.tournament.realized)} USD`]);
    return (
        <div className="ui-stats">
            {items.map(([label, bal, ini, note]) => (
                <Stat
                    key={label}
                    label={label}
                    value={`${money(bal)} USD`}
                    tone={tone(bal - ini)}
                    sub={`${signed(bal - ini)} (${signed(pct(bal, ini), " %")}) · ${note}`}
                />
            ))}
        </div>
    );
}

export default Summary;
