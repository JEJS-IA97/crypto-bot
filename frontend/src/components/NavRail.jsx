import { TABS } from "./tabs";

const ICON_PATHS = {
    operar: (
        <path
            d="M5 19V11M12 19V5M19 19v-6"
            strokeLinecap="round"
        />
    ),
    estado: (
        <path
            d="M3 13h4l2.5-7 4 14 2.5-7H21"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    ),
    historial: (
        <path
            d="M4 6h16M4 12h16M4 18h10"
            strokeLinecap="round"
        />
    ),
};

function scrollToWorkspace(onSelect, tabId) {
    onSelect(tabId);

    const reduce = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    document.getElementById("workspace")?.scrollIntoView({
        behavior: reduce ? "auto" : "smooth",
        block: "start",
    });
}

function NavRail({ active, onSelect }) {
    return (
        <nav className="rail" aria-label="Secciones del panel">
            <button
                type="button"
                className="rail-brand"
                aria-label="Ir al inicio"
                onClick={() => window.scrollTo({ top: 0 })}
            >
                <svg
                    aria-hidden="true"
                    focusable="false"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                >
                    <path d="M12 3l7 9-7 9-7-9z" />
                </svg>
            </button>

            <ul className="rail-nav">
                {TABS.map((tab) => (
                    <li key={tab.id}>
                        <button
                            type="button"
                            className="rail-link"
                            aria-label={tab.label}
                            aria-current={
                                active === tab.id ? "true" : undefined
                            }
                            onClick={() =>
                                scrollToWorkspace(onSelect, tab.id)
                            }
                        >
                            <svg
                                aria-hidden="true"
                                focusable="false"
                                width="20"
                                height="20"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.7"
                            >
                                {ICON_PATHS[tab.id]}
                            </svg>
                        </button>
                    </li>
                ))}
            </ul>

            <button
                type="button"
                className="rail-action"
                aria-label="Nueva orden"
                onClick={() => scrollToWorkspace(onSelect, "operar")}
            >
                <svg
                    aria-hidden="true"
                    focusable="false"
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                >
                    <path d="M12 5v14M5 12h14" />
                </svg>
            </button>
        </nav>
    );
}

export default NavRail;
