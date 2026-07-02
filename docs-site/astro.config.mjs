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
				'Interne technische Dokumentation: Architektur, KI-Pipeline und Architekturentscheidungen.',
			defaultLocale: 'root',
			locales: {
				root: { label: 'Deutsch', lang: 'de' },
			},
			pagination: true,
			sidebar: [
				{ label: 'Architektur', items: [{ slug: 'architektur' }] },
				{
					label: 'KI & Qualität',
					items: [
						{ slug: 'ki-pipeline' },
						{ slug: 'eval' },
					],
				},
				{
					label: 'Produkt',
					items: [{ slug: 'beschluesse' }],
				},
				{
					label: 'Entscheidungen (ADRs)',
					items: [{ autogenerate: { directory: 'adr' } }],
				},
			],
		}),
	],
});
