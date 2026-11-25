// @ts-check
import { defineConfig } from 'astro/config';
import { satteri } from '@astrojs/markdown-satteri';
import starlight from '@astrojs/starlight';

/**
 * Deutsche Schlusszeichen: „…“ statt „…”.
 *
 * Die Quellen schreiben das Schlusszeichen meist gerade („Ähnliche
 * Beschlüsse"). Der Markdown-Prozessor Sätteri macht daraus seit 0.10.0 ein ”,
 * weil er ein unpaariges schließendes " als englisches Schlusszeichen setzt;
 * bis 0.9 wurde es ein “ — für deutschen Text das richtige, aber Zufall. Eine
 * Sprachoption hat Sätteri nicht.
 *
 * Das Plugin wandelt NUR ein ”, das ein offenes „ schließt. Englische
 * Anführungen (“…”), Zollzeichen und alles in Code bleiben, wie sie sind: Code
 * ist kein Textknoten, und ohne offenes „ wird nichts angefasst. Gezählt wird
 * je Absatz, Überschrift, Listenpunkt und Tabellenzelle neu, damit ein
 * vergessenes Schlusszeichen nicht in den nächsten Block wirkt.
 *
 * Kann weg, sobald Sätteri (oder Astro) die Anführungszeichen nach der Sprache
 * der Seite setzt — oder sobald die Quellen durchgehend „…“ schreiben.
 *
 * Eine Fabrik und kein festes Objekt: Sätteri ruft sie je Dokument einmal,
 * der Zähler gehört damit genau einem Dokument.
 */
const germanClosingQuotes = () => {
	let open = 0;
	const reset = () => {
		open = 0;
	};
	return {
		name: 'german-closing-quotes',
		paragraph: reset,
		heading: reset,
		listItem: reset,
		tableCell: reset,
		/**
		 * @param {{ value: string }} node
		 * @param {{ setProperty: (node: any, key: 'value', value: string) => void }} ctx
		 */
		text(node, ctx) {
			let changed = false;
			const value = [...node.value]
				.map((ch) => {
					if (ch === '„') open++;
					else if (ch === '“' && open > 0) open--;
					else if (ch === '”' && open > 0) {
						open--;
						changed = true;
						return '“';
					}
					return ch;
				})
				.join('');
			if (changed) ctx.setProperty(node, 'value', value);
		},
	};
};

// Ausgeliefert unter ratslotse.de/docs (statische Site, hinter Caddy/Next).
// https://astro.build/config
export default defineConfig({
	site: 'https://ratslotse.de',
	base: '/docs',
	markdown: {
		processor: satteri({ mdastPlugins: [germanClosingQuotes] }),
	},
	integrations: [
		starlight({
			title: 'Ratslotse — Technik',
			// Dieselbe Kachel wie das App-Icon (scripts/brand_icons.py). Vorher
			// stand hier gar nichts, und die Doku trug Starlights Standard-Stern.
			favicon: '/favicon.png',
			description:
				'Technische Dokumentation zu ratslotse.de: Architektur, KI-Pipeline und Architekturentscheidungen.',
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/Schereo/Ratslotse' },
			],
			defaultLocale: 'root',
			locales: {
				root: { label: 'Deutsch', lang: 'de' },
			},
			pagination: true,
			sidebar: [
				{ label: '↩ Zurück zur App', link: 'https://ratslotse.de/dashboard' },
				{
					label: 'Architektur',
					items: [
						{ slug: 'architektur' },
						{ slug: 'betrieb' },
					],
				},
				{
					label: 'KI & Qualität',
					items: [
						{ slug: 'ki-pipeline' },
						{ slug: 'frag-den-rat' },
						{ slug: 'bewertungen' },
						{ slug: 'eval' },
					],
				},
				{
					label: 'Produkt',
					items: [
						{ slug: 'beschluesse' },
						{ slug: 'sitzungen' },
						{ slug: 'mein-viertel' },
						{ slug: 'plaene' },
						{ slug: 'andere-staedte' },
						{ slug: 'haushalt' },
						{ slug: 'haushalt-quellen-recherche' },
						{ slug: 'wahlabend' },
						{ slug: 'tippspiel' },
						{ slug: 'app-und-konten' },
						{ slug: 'mcp' },
					],
				},
				{
					// Erzeugt aus den Registern im Code (scripts/docs_reference.py).
					label: 'Referenz',
					items: [{ autogenerate: { directory: 'referenz' } }],
				},
				{
					label: 'Entscheidungen (ADRs)',
					items: [{ autogenerate: { directory: 'adr' } }],
				},
			],
		}),
	],
});
