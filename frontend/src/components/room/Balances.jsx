import { money, signed, tone } from "./fmt";

function Group({ title, initial, balance, extra }) {
    const pnl = balance - initial;
    const pct = initial ? (pnl / initial) * 100 : 0;
    return (
        <div className="bal-group">
            <h2>{title}</h2>
            <dl>
                <div>
                    <dt>Saldo inicial</dt>
                    <dd className="num">{money(initial)}</dd>
                </div>
                <div>
                    <dt>Saldo actual</dt>
                    <dd className="num strong">{money(balance)}</dd>
                </div>
                <div>
                    <dt>Ganancia / pérdida</dt>
                    <dd className={`num ${tone(pnl)}`}>
                        {signed(pnl)} <span className="small">({signed(pct, " %")})</span>
                    </dd>
                </div>
                {extra}
            </dl>
        </div>
    );
}

function Balances({ board }) {
    const b = board?.balances;
    if (!b) return null;
    const { main, tournament: t } = b;
    return (
        <section className="panel balances" aria-label="Saldos">
            {main && (
                <Group
                    title="Cuenta principal · tendencia diaria BTC+ETH"
                    initial={main.initial}
                    balance={main.balance}
                    extra={
                        <div>
                            <dt>Disponible · posiciones</dt>
                            <dd className="num">
                                {money(main.available)} · {main.open_positions}
                            </dd>
                        </div>
                    }
                />
            )}
            {b.copier && (
                <Group
                    title="Copia de ganadoras · paper"
                    initial={b.copier.initial}
                    balance={b.copier.balance}
                    extra={
                        <div>
                            <dt>Copia a</dt>
                            <dd>
                                {b.copier.copies?.length
                                    ? b.copier.copies.join(", ")
                                    : "nadie aún · espera en USDT hasta que algo gane 5 largos"}
                            </dd>
                        </div>
                    }
                />
            )}
            <Group
                title={`Torneo · ${t.accounts} cuentas virtuales`}
                initial={t.initial}
                balance={t.balance}
                extra={
                    <div>
                        <dt>Realizado (cerradas)</dt>
                        <dd className={`num ${tone(t.realized)}`}>{signed(t.realized)}</dd>
                    </div>
                }
            />
        </section>
    );
}

export default Balances;
