import { useEffect, useRef, useState } from "react";

/** Llama a `fetcher` al montar y cada `ms`; conserva el último dato bueno. */
export default function usePoll(fetcher, ms) {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const latest = useRef(fetcher);

    useEffect(() => {
        latest.current = fetcher;
    });

    useEffect(() => {
        let alive = true;
        const run = async () => {
            try {
                const next = await latest.current();
                if (alive) {
                    setData(next);
                    setError("");
                }
            } catch (err) {
                if (alive) setError(err?.response?.data?.detail || "Sin conexión con el bot");
            }
        };
        run();
        const timer = setInterval(run, ms);
        return () => {
            alive = false;
            clearInterval(timer);
        };
    }, [ms]);

    return { data, error };
}
