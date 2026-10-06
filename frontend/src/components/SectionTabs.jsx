import { useRef } from "react";

import { TABS } from "./tabs";

function SectionTabs({ value, onChange }) {
    const listRef = useRef(null);

    const handleKeyDown = (event) => {
        const index = TABS.findIndex((tab) => tab.id === value);
        let nextIndex;

        if (event.key === "ArrowLeft") {
            nextIndex = (index - 1 + TABS.length) % TABS.length;
        } else if (event.key === "ArrowRight") {
            nextIndex = (index + 1) % TABS.length;
        } else if (event.key === "Home") {
            nextIndex = 0;
        } else if (event.key === "End") {
            nextIndex = TABS.length - 1;
        } else {
            return;
        }

        event.preventDefault();
        onChange(TABS[nextIndex].id);

        const buttons = listRef.current?.querySelectorAll('[role="tab"]');
        buttons?.[nextIndex]?.focus();
    };

    return (
        <div
            className="section-tabs"
            role="tablist"
            aria-label="Secciones del panel"
            ref={listRef}
            onKeyDown={handleKeyDown}
        >
            {TABS.map((tab) => (
                <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    id={`tab-${tab.id}`}
                    className="section-tab"
                    aria-controls={`panel-${tab.id}`}
                    aria-selected={value === tab.id}
                    tabIndex={value === tab.id ? 0 : -1}
                    onClick={() => onChange(tab.id)}
                >
                    {tab.label}
                </button>
            ))}
        </div>
    );
}

export default SectionTabs;
