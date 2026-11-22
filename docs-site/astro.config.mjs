// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// Ausgeliefert unter ratslotse.de/docs (statische Site, hinter Caddy/Next).
// https://astro.build/config
export default defineConfig({
	site: 'https://ratslotse.de',
	base: '/docs',
	integrations: [
		starlight({
			title: 'Ratslotse — Technik',
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
