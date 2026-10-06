import { useState } from "react";

import { clearToken, getToken, setToken } from "../api/client";

function TokenField() {
    const [value, setValue] = useState("");
    const [hasToken, setHasToken] = useState(() =>
        Boolean(getToken())
    );
    const [message, setMessage] = useState("");

    const handleSave = () => {
        const trimmed = value.trim();
        if (!trimmed) {
            return;
        }

        setToken(trimmed);
        setHasToken(true);
        setValue("");
        setMessage("Token guardado en este navegador.");
    };

    const handleClear = () => {
        clearToken();
        setHasToken(false);
        setValue("");
        setMessage("Token eliminado.");
    };

    return (
        <section
            className="panel-card token-field"
            data-testid="token-field"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">TOKEN DE CONTROL</span>
                    <h2>Acceso remoto</h2>
                </div>

                {hasToken && (
                    <span
                        className="panel-caption state-active"
                        data-testid="token-status"
                    >
                        Guardado
                    </span>
                )}
            </div>

            <p className="kill-note">
                Introduce el API_TOKEN para detener o arrancar el
                bot desde cualquier lugar. El token se guarda solo
                en este navegador.
            </p>

            <label className="token-label" htmlFor="api-token">
                Token de control
            </label>

            <input
                id="api-token"
                type="password"
                autoComplete="off"
                placeholder="Pega aquí el token de control"
                value={value}
                onChange={(event) => setValue(event.target.value)}
            />

            {message && (
                <div className="form-message success">{message}</div>
            )}

            <div className="token-actions">
                <button
                    type="button"
                    className="btn btn-primary btn-block"
                    onClick={handleSave}
                    disabled={!value.trim()}
                >
                    Guardar
                </button>

                {hasToken && (
                    <button
                        type="button"
                        className="btn btn-danger btn-block"
                        onClick={handleClear}
                    >
                        Quitar
                    </button>
                )}
            </div>
        </section>
    );
}

export default TokenField;
