import { readFileSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

/**
 * Carga el CSS tal y como lo importa la app: index.css más cada
 * archivo referenciado con @import, en orden (D-7).
 */
export function loadCssFiles() {
    const srcDir = join(process.cwd(), "src");
    const entry = readFileSync(join(srcDir, "index.css"), "utf8");
    const files = [{ name: "index.css", content: entry }];

    const importRe = /@import\s+"\.\/styles\/([^"]+)";/g;
    let match = importRe.exec(entry);

    while (match) {
        files.push({
            name: match[1],
            content: readFileSync(
                join(srcDir, "styles", match[1]),
                "utf8"
            ),
        });
        match = importRe.exec(entry);
    }

    return files;
}

export function loadCss() {
    return loadCssFiles()
        .map((file) => file.content)
        .join("\n");
}
