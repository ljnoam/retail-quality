import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const SKILL_DIR = "/Users/noamleclapart-jublot/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const RUNTIME_PYTHON = "/Users/noamleclapart-jublot/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const FINAL_PPTX = path.join(workspaceDir, "presentation", "retail-quality-soutenance-rncp-c2-c3-corrige.pptx");
const stagingDir = path.join(workspaceDir, ".codex-finalizer");

const { applyPresentationChartFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

const FONT = "Helvetica";
const MONO = "Menlo";
const C = {
  ink: "#11233B",
  navy: "#173B57",
  cyan: "#1B8A9B",
  orange: "#E56B3F",
  cream: "#F6F2EA",
  paper: "#FFFCF7",
  muted: "#5E6D78",
  line: "#D8D2C7",
  green: "#2F7D64",
  amber: "#C88B2B",
  red: "#B54A45",
  bluePale: "#DCECF0",
  orangePale: "#F8E3D9",
  grayPale: "#EEEAE3",
};

const report = JSON.parse(await fs.readFile(path.join(workspaceDir, "output/rapport_qualite.json"), "utf8"));
const bq = JSON.parse(await fs.readFile(path.join(workspaceDir, "evidence/mesures_des_requetes/bigquery_sales_job.json"), "utf8"));
const dry = JSON.parse(await fs.readFile(path.join(workspaceDir, "evidence/mesures_des_requetes/bigquery_dry_runs.json"), "utf8"));
const pg = JSON.parse(await fs.readFile(path.join(workspaceDir, "evidence/mesures_des_requetes/postgres_job.json"), "utf8"));
const verification = JSON.parse(await fs.readFile(path.join(workspaceDir, "evidence/rapport_de_tests/c3_output_verification.json"), "utf8"));
const acceptedCsv = (await fs.readFile(path.join(workspaceDir, "output/ventes_fiables.csv"), "utf8")).trim().split(/\r?\n/);
const quarantineCsv = (await fs.readFile(path.join(workspaceDir, "output/quarantaine.csv"), "utf8")).trim().split(/\r?\n/);

if (report.accounted_rows !== report.input_sales_rows) throw new Error("Volumes non réconciliés");
if (acceptedCsv.length - 1 !== report.final_rows) throw new Error("Nombre de lignes finales incohérent");
if (quarantineCsv.length - 1 !== report.quarantine_rows) throw new Error("Nombre de lignes de quarantaine incohérent");
if (Object.values(verification.checks).some((v) => v !== "PASSED")) throw new Error("Contrôle C3 non réussi");

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function addText(slide, text, x, y, w, h, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: options.fill ?? "none",
    line: options.line ?? { fill: "none", width: 0 },
    borderRadius: options.borderRadius,
  });
  shape.text = text;
  shape.text.style = {
    typeface: options.typeface ?? FONT,
    fontSize: options.fontSize ?? 22,
    bold: options.bold ?? false,
    color: options.color ?? C.ink,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
    insets: options.insets ?? { left: 6, right: 6, top: 4, bottom: 4 },
  };
  return shape;
}

function addRule(slide, x, y, w, color = C.line, height = 2) {
  return slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width: w, height },
    fill: color,
    line: { fill: "none", width: 0 },
  });
}

function addTitle(slide, number, title, subtitle = "") {
  slide.background.fill = C.paper;
  addText(slide, String(number).padStart(2, "0"), 58, 42, 58, 34, { fontSize: 16, bold: true, color: C.orange });
  addText(slide, title, 112, 36, 1088, 62, { fontSize: 34, bold: true, color: C.ink, verticalAlignment: "middle" });
  addRule(slide, 64, 108, 1152, C.line, 1);
  if (subtitle) addText(slide, subtitle, 72, 114, 1120, 34, { fontSize: 16, color: C.muted });
}

function addFooter(slide, source, n) {
  addRule(slide, 64, 674, 1152, C.line, 1);
  addText(slide, `${source}     ${n}/12`, 68, 680, 1130, 22, { fontSize: 11, color: C.muted, verticalAlignment: "middle" });
}

function notes(slide, items) {
  slide.speakerNotes.textFrame.setText(items);
  slide.speakerNotes.setVisible(true);
}

function styleTable(table, rows, columns, options = {}) {
  table.borders.assign({ style: "solid", fill: C.line, width: 1 });
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: columns }).assign({
    fill: options.headerFill ?? C.navy,
    textStyle: { typeface: FONT, fontSize: options.headerSize ?? 16, bold: true, color: "#FFFFFF" },
    margins: { left: 8, right: 8, top: 6, bottom: 6 },
    anchor: "middle",
  });
  if (rows > 1) {
    table.cells.block({ row: 1, column: 0, rowCount: rows - 1, columnCount: columns }).assign({
      textStyle: { typeface: options.typeface ?? FONT, fontSize: options.fontSize ?? 15, color: C.ink },
      margins: { left: 8, right: 8, top: 5, bottom: 5 },
      anchor: "middle",
    });
  }
  for (let r = 1; r < rows; r += 1) {
    if (r % 2 === 0) table.cells.block({ row: r, column: 0, rowCount: 1, columnCount: columns }).fill = C.grayPale;
  }
}

// 1 — couverture
{
  const s = presentation.slides.add();
  s.background.fill = C.ink;
  addText(s, "RETAIL QUALITY", 72, 74, 350, 38, { fontSize: 17, bold: true, color: "#8ED6DF" });
  addText(s, "Fiabiliser des ventes avant le reporting financier", 72, 150, 1010, 158, { fontSize: 50, bold: true, color: "#FFFFFF", verticalAlignment: "middle" });
  addText(s, "POC exécutable pour RNCP BC01 C2 et C3", 76, 326, 850, 48, { fontSize: 24, color: "#D8E6EC" });
  addRule(s, 76, 404, 180, C.orange, 6);
  addText(s, "Données publiques de substitution utilisées afin de préserver\nla confidentialité des données d’entreprise.", 76, 440, 980, 100, { fontSize: 22, color: "#F5EDE5" });
  addText(s, "Noam Leclapart-Jublot  |  Soutenance du 19 septembre 2026", 76, 635, 1080, 32, { fontSize: 16, color: "#AFC4CF" });
  notes(s, [
    "Ouverture orale : je présente un prototype de contrôle de qualité avant calcul d'un montant en euros.",
    "Je précise immédiatement que TheLook est fictif et remplace des données d'entreprise afin d'éviter toute divulgation.",
    "La précision sur l'absence de déploiement apparaît dans les limites, en dernière slide. Ici, je garde l'ouverture centrée sur la confidentialité.",
  ]);
}

// 2 — problème
{
  const s = presentation.slides.add();
  addTitle(s, 2, "Question métier et critère de décision");
  addText(s, "Quelles lignes de ventes peut-on utiliser pour calculer un chiffre d’affaires en euros ?", 76, 148, 1110, 74, { fontSize: 30, bold: true, color: C.navy, verticalAlignment: "middle" });
  addText(s, "Une ligne exploitable doit réunir quatre preuves", 76, 252, 530, 40, { fontSize: 20, bold: true, color: C.orange });
  const labels = [
    ["1", "Identifiants et date valides"],
    ["2", "État commercial admissible"],
    ["3", "Prix strictement positif"],
    ["4", "Taux BCE antérieur de 0 à 7 jours"],
  ];
  labels.forEach(([n, t], i) => {
    addText(s, n, 84, 310 + i * 66, 38, 38, { fontSize: 18, bold: true, color: "#FFFFFF", alignment: "center", verticalAlignment: "middle", fill: i === 3 ? C.cyan : C.navy, borderRadius: 19 });
    addText(s, t, 138, 304 + i * 66, 520, 50, { fontSize: 21, color: C.ink, verticalAlignment: "middle" });
  });
  addText(s, "Sortie attendue", 744, 252, 420, 40, { fontSize: 20, bold: true, color: C.orange });
  addText(s, "Un jeu final unique pour les lignes acceptées", 744, 312, 430, 70, { fontSize: 25, bold: true, color: C.ink });
  addText(s, "Chaque autre ligne reçoit un statut, un code de raison stable et une explication lisible.", 744, 402, 430, 110, { fontSize: 21, color: C.muted });
  addText(s, "Le rapport conserve exactement les 2 131 lignes d’entrée.", 744, 548, 430, 58, { fontSize: 20, bold: true, color: C.green });
  addFooter(s, "Source : PRD.md, output/rapport_qualite.json", 2);
  notes(s, [
    "J'explique que le besoin ne consiste pas à corriger silencieusement toutes les lignes. Il faut décider si elles entrent dans le calcul et conserver la raison.",
    "Le statut métier et la qualité technique restent séparés : une annulation valide n'est pas une corruption.",
    "La conservation des volumes permet de détecter toute perte ou duplication pendant le pipeline.",
  ]);
}

// 3 — sources et architecture
{
  const s = presentation.slides.add();
  addTitle(s, 3, "Sources publiques et architecture du POC", "Période fixe : ventes du 1er au 31 janvier 2024; taux du 25 décembre 2023 au 31 janvier 2024");
  const boxes = [
    { x: 70, y: 220, w: 250, h: 130, title: "BigQuery", body: "TheLook fictif\norders + order_items + products\n2 131 lignes", fill: C.bluePale },
    { x: 70, y: 420, w: 250, h: 130, title: "PostgreSQL", body: "Taux BCE USD/EUR\nrate_sources + exchange_rates\n25 observations", fill: C.orangePale },
    { x: 455, y: 300, w: 320, h: 170, title: "Pipeline Python", body: "Validation du schéma\nNormalisation et contrôles\nRapprochement temporel\nCalcul décimal", fill: C.grayPale },
    { x: 910, y: 210, w: 275, h: 95, title: "Jeu final", body: "1 167 lignes acceptées", fill: "#DCEDE5" },
    { x: 910, y: 340, w: 275, h: 95, title: "Quarantaine", body: "964 lignes expliquées", fill: "#F8E8C7" },
    { x: 910, y: 470, w: 275, h: 95, title: "Rapport", body: "Volumes, raisons, hashes", fill: "#E8E1EE" },
  ];
  const created = boxes.map((b) => {
    const sh = s.shapes.add({ geometry: "roundRect", position: { left: b.x, top: b.y, width: b.w, height: b.h }, fill: b.fill, line: { style: "solid", fill: C.line, width: 1 }, borderRadius: 18 });
    sh.text = [[{ run: b.title, textStyle: { bold: true, fontSize: "20pt", typeface: FONT, color: C.navy } }], [{ run: b.body, textStyle: { fontSize: "14pt", typeface: FONT, color: C.ink } }]];
    sh.text.style = { typeface: FONT, fontSize: 18, color: C.ink, verticalAlignment: "middle", alignment: "center", autoFit: "shrinkText", insets: { left: 10, right: 10, top: 8, bottom: 8 } };
    return sh;
  });
  s.shapes.connect(created[0], created[2], { kind: "elbow", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.cyan, width: 3 } });
  s.shapes.connect(created[1], created[2], { kind: "elbow", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.orange, width: 3 } });
  [3, 4, 5].forEach((idx) => s.shapes.connect(created[2], created[idx], { kind: "elbow", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.navy, width: 2 } }));
  addFooter(s, "Sources : TheLook public sur BigQuery; BCE EXR.D.USD.EUR.SP00.A", 3);
  notes(s, [
    "Je montre les deux systèmes réellement interrogés : BigQuery pour les ventes et PostgreSQL local pour le référentiel BCE.",
    "Les snapshots figés rendent le résultat rejouable hors connexion. Les scripts d'extraction permettent aussi de refaire les appels quand les accès sont disponibles.",
    "La période fixe évite que les chiffres changent le jour de la soutenance.",
    "Limite à annoncer : le schéma TheLook expose sale_price comme FLOAT sans devise documentée. Le pipeline l'interprète comme USD uniquement pour le POC.",
  ]);
}

// 4 — BigQuery
{
  const s = presentation.slides.add();
  addTitle(s, 4, "C2 — Extraction BigQuery exécutée", "Grain : une ligne par order_item; les états ne sont pas filtrés afin de conserver les exclusions et les cas à vérifier");
  addText(s, "SQL versionné", 72, 154, 520, 32, { fontSize: 18, bold: true, color: C.orange });
  const sql = "SELECT\n  oi.order_id, oi.id AS order_item_id, oi.product_id,\n  DATE(oi.created_at, 'UTC') AS sale_date_utc,\n  o.status AS order_status, oi.status AS item_status,\n  oi.sale_price, p.category AS product_category\nFROM `...order_items` oi\nLEFT JOIN `...orders` o ON o.order_id = oi.order_id\nLEFT JOIN `...products` p ON p.id = oi.product_id\nWHERE oi.created_at >= TIMESTAMP('2024-01-01', 'UTC')\n  AND oi.created_at <  TIMESTAMP('2024-02-01', 'UTC')";
  addText(s, sql, 72, 190, 590, 410, { fontSize: 15, typeface: MONO, color: "#EAF3F6", fill: C.ink, insets: { left: 16, right: 16, top: 14, bottom: 12 } });
  addText(s, "Extrait réel", 705, 154, 475, 32, { fontSize: 18, bold: true, color: C.orange });
  const table = s.tables.add({ rows: 5, columns: 4, left: 705, top: 190, width: 480, height: 235, values: [
    ["item", "date UTC", "statut", "prix"],
    ["140", "2024-01-22", "Cancelled", "48.00"],
    ["331", "2024-01-28", "Complete", "99.949996…"],
    ["388", "2024-01-12", "Returned", "39.50"],
    ["413", "2024-01-30", "Returned", "16.50"],
  ] });
  styleTable(table, 5, 4, { fontSize: 14 });
  addText(s, "Job 4fb47302-bc09-449f-b2aa-6cbfe12d0e5c", 705, 454, 480, 32, { fontSize: 15, bold: true, color: C.navy });
  addText(s, "2 131 lignes  ·  12 003 113 octets traités  ·  69 slot-ms  ·  cache absent", 705, 493, 480, 78, { fontSize: 20, color: C.ink });
  addText(s, "LEFT JOIN : les références absentes restent visibles pour le contrôle qualité.", 705, 588, 480, 48, { fontSize: 16, color: C.muted });
  addFooter(s, "sql/bigquery_sales.sql; evidence/mesures_des_requetes/bigquery_sales_job.json", 4);
  notes(s, [
    "Je commence par le grain : order_items est la table motrice et oi.id porte la clé de ligne.",
    "Les LEFT JOIN conservent une ligne même si sa commande ou son produit manque. Le contrôle qualité doit voir cette anomalie au lieu de la supprimer dans SQL.",
    "Le filtre utilise une borne de début incluse et une borne de fin exclue, toutes deux en UTC.",
    "Je n'extrais aucun nom, courriel ou adresse. Les neuf colonnes répondent directement aux règles C3.",
    `Preuve : job ${bq.job.job_id}, état ${bq.job.state}, ${bq.result_rows} lignes.`,
  ]);
}

// 5 — PostgreSQL
{
  const s = presentation.slides.add();
  addTitle(s, 5, "C2 — Extraction PostgreSQL exécutée", "La jointure ajoute la paire, la série et l’URL de provenance à chaque observation BCE");
  const sql = "SELECT\n  r.rate_date, s.quote_currency, s.base_currency,\n  r.usd_per_eur, r.observation_status,\n  s.series_key, s.source_url\nFROM exchange_rates r\nINNER JOIN rate_sources s ON s.source_id = r.source_id\nWHERE s.series_key = 'EXR.D.USD.EUR.SP00.A'\n  AND r.rate_date >= DATE '2024-01-01' - INTERVAL '7 days'\n  AND r.rate_date <  DATE '2024-02-01'\nORDER BY r.rate_date;";
  addText(s, "SQL versionné", 82, 150, 500, 36, { fontSize: 18, bold: true, color: C.orange, autoFit: "none" });
  addText(s, sql, 72, 195, 590, 375, { fontSize: 15, typeface: MONO, color: "#EAF3F6", fill: C.ink, insets: { left: 16, right: 16, top: 14, bottom: 12 } });
  addText(s, "Extrait réel", 705, 154, 475, 32, { fontSize: 18, bold: true, color: C.orange });
  const table = s.tables.add({ rows: 6, columns: 3, left: 705, top: 190, width: 480, height: 260, values: [
    ["date", "USD / EUR", "statut"],
    ["2023-12-27", "1.10650000", "A"],
    ["2023-12-28", "1.11140000", "A"],
    ["2023-12-29", "1.10500000", "A"],
    ["2024-01-02", "1.09560000", "A"],
    ["2024-01-03", "1.09190000", "A"],
  ] });
  styleTable(table, 6, 3, { fontSize: 14 });
  addText(s, "25 taux  ·  PostgreSQL 17.11  ·  27/12/2023 au 31/01/2024", 705, 478, 480, 64, { fontSize: 21, bold: true, color: C.navy });
  addText(s, "Un taux sans source valide ne peut pas entrer dans la conversion.", 705, 565, 480, 48, { fontSize: 17, color: C.muted });
  addFooter(s, "sql/postgres_rates.sql; evidence/.../postgres_job.json", 5);
  notes(s, [
    "La table exchange_rates contient les dates et valeurs. La table rate_sources porte la série, les devises et l'URL officielle.",
    "INNER JOIN est volontaire : une observation sans source valide ne doit pas servir au calcul.",
    "La fenêtre commence sept jours avant janvier afin de couvrir les jours sans publication, notamment le week-end et les jours fériés.",
    "La série BCE exprime des USD pour 1 EUR. La formule correcte consiste donc à diviser le montant supposé USD par le taux.",
  ]);
}

// 6 — optimisation
{
  const s = presentation.slides.add();
  addTitle(s, 6, "C2 — Mesures d’optimisation et limites", "Les comparaisons distinguent une estimation de dry run, un job exécuté et un plan PostgreSQL réel");
  const chart = s.charts.add("bar", {
    position: { left: 62, top: 170, width: 650, height: 370 },
    categories: ["Projection large", "Projection finale"],
    series: [{ name: "Millions d’octets estimés", values: [dry.baseline.total_bytes_processed / 1000000, dry.final.total_bytes_processed / 1000000], valuesFormatCode: "0.0\" M\"", fill: C.cyan, points: [{ idx: 0, fill: C.orange }, { idx: 1, fill: C.cyan }] }],
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 55 },
    hasLegend: false,
    xAxis: { numberFormatCode: "0\" M\"", min: 0, max: 30, majorUnit: 5, majorGridlines: { style: "solid", fill: C.line, width: 1 }, textStyle: { fill: C.muted, fontSize: 12 } },
    yAxis: { textStyle: { fill: C.ink, fontSize: 16, bold: true }, line: { fill: C.line, width: 1 } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fill: C.ink, fontSize: 13, bold: true } },
    chartFill: "#FFFCF7",
    plotAreaFill: "#FFFCF7",
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });
  addText(s, "−51,33 % d’octets estimés", 92, 548, 560, 42, { fontSize: 26, bold: true, color: C.green, alignment: "center" });
  addText(s, "BigQuery", 770, 166, 420, 30, { fontSize: 18, bold: true, color: C.orange });
  addText(s, "Job final", 770, 210, 160, 28, { fontSize: 16, color: C.muted });
  addText(s, "12 003 113 octets traités\n31 457 280 octets dans le champ facturable\n69 slot-ms, 343 ms de travail SQL", 770, 242, 420, 105, { fontSize: 19, color: C.ink });
  addText(s, "Pourquoi plus d’octets facturables ? Trois tables sont référencées. Le minimum technique de 10 MiB par table donne 30 MiB, soit 31 457 280 octets.", 770, 338, 420, 58, { fontSize: 14, color: C.muted });
  addText(s, "PostgreSQL", 770, 410, 420, 30, { fontSize: 18, bold: true, color: C.orange });
  addText(s, "Index couvrant utilisé\n4 blocs en cache, 0 bloc lu du disque\n0,022 ms d’exécution serveur", 770, 446, 420, 92, { fontSize: 19, color: C.ink });
  addText(s, "Aucun gain de durée n’est revendiqué. Les tables BigQuery ne sont pas partitionnées selon les métadonnées relevées.", 770, 554, 420, 82, { fontSize: 16, color: C.red, bold: true });
  addFooter(s, "evidence/mesures_des_requetes/bigquery_dry_runs.json; postgres_job.json", 6);
  notes(s, [
    "La comparaison BigQuery conserve les mêmes jointures et le même filtre. Elle change surtout la projection des colonnes.",
    "Le dry run estime 24 664 270 octets pour la version large et 12 003 113 pour la version finale, soit 51,33 % de moins.",
    "Les 31 457 280 octets facturables sont supérieurs aux 12 003 113 octets traités à cause de l'arrondi minimal de facturation par table. La requête référence trois tables et le minimum technique représente 10 485 760 octets par table, donc exactement 31 457 280 octets. Ce champ ne prouve pas qu'une somme a été payée, notamment avec le quota gratuit ou le Sandbox.",
    "Je parle d'octets estimés, pas d'un temps gagné. Les dry runs ne fournissent pas une comparaison de durée.",
    "PostgreSQL utilise l'index couvrant, mais 25 lignes restent trop peu pour attribuer un gain de temps fiable à l'index.",
  ]);
}

// 7 — algorithme
{
  const s = presentation.slides.add();
  addTitle(s, 7, "C3 — Ordre déterministe de l’algorithme");
  const steps = [
    ["1", "Valider", "Fichiers, en-têtes, colonnes"],
    ["2", "Normaliser", "IDs, dates UTC, décimaux, libellés"],
    ["3", "Contrôler", "Corruptions et doublons"],
    ["4", "Décider", "Qualité puis règle métier"],
    ["5", "Rapprocher", "Dernier taux antérieur, max. 7 jours"],
    ["6", "Calculer", "USD ÷ USD/EUR, arrondi par ligne"],
    ["7", "Écrire", "Final, quarantaine, rapport"],
  ];
  steps.forEach(([n, t, b], i) => {
    const y = 150 + i * 70;
    addText(s, n, 78, y, 42, 42, { fontSize: 18, bold: true, color: "#FFFFFF", alignment: "center", verticalAlignment: "middle", fill: i < 3 ? C.navy : (i < 6 ? C.cyan : C.orange), borderRadius: 21 });
    addText(s, t, 142, y - 2, 220, 45, { fontSize: 22, bold: true, color: C.ink, verticalAlignment: "middle" });
    addText(s, b, 372, y - 2, 720, 45, { fontSize: 20, color: C.muted, verticalAlignment: "middle" });
    if (i < steps.length - 1) addRule(s, 99, y + 46, 2, C.line, 22);
  });
  addText(s, "Le premier motif applicable devient la décision principale. Aucune ligne ne change de statut selon l’ordre du CSV.", 760, 580, 420, 70, { fontSize: 17, bold: true, color: C.navy, fill: C.bluePale, borderRadius: 12, verticalAlignment: "middle" });
  addFooter(s, "src/build_dataset.py; src/quality_rules.py; docs/algorithme-et-regles-qualite.md", 7);
  notes(s, [
    "L'ordre compte : je valide et normalise avant de chercher un taux ou d'appliquer une règle métier.",
    "Les doublons sont détectés après normalisation des identifiants. Toutes les occurrences sont rejetées, ce qui évite de choisir arbitrairement une ligne.",
    "Le rapprochement n'utilise jamais un taux futur. Sept jours calendaires constituent la borne inclusive du POC.",
    "La conversion et l'arrondi viennent en dernier, uniquement pour une ligne admissible.",
  ]);
}

// 8 — règles
{
  const s = presentation.slides.add();
  addTitle(s, 8, "C3 — Règles, décisions et codes de raison", "Les anomalies fabriquées vivent uniquement dans tests/fixtures; les résultats publics n’en contiennent aucune ajoutée artificiellement");
  const values = [
    ["Condition", "Décision", "Code stable"],
    ["Clé répétée", "REJETÉE", "DUPLICATE_LINE_ID"],
    ["ID, date ou prix invalide", "REJETÉE", "INVALID_* / NON_POSITIVE_PRICE"],
    ["Statuts contradictoires", "À VÉRIFIER", "STATUS_CONFLICT"],
    ["Commande annulée", "EXCLUE MÉTIER", "CANCELLED_ORDER"],
    ["Commande retournée", "EXCLUE MÉTIER", "RETURNED_ORDER"],
    ["Commande en traitement", "À VÉRIFIER", "PROCESSING_ORDER"],
    ["Catégorie absente", "À VÉRIFIER", "MISSING_PRODUCT_CATEGORY"],
    ["Aucun taux admissible", "À VÉRIFIER", "NO_PRIOR_RATE / RATE_TOO_OLD"],
    ["Tous les contrôles passent", "ACCEPTÉE", "aucun motif d’exclusion"],
  ];
  const table = s.tables.add({ rows: values.length, columns: 3, left: 74, top: 166, width: 1130, height: 440, values });
  styleTable(table, values.length, 3, { fontSize: 14, headerSize: 16 });
  table.columns.get(0).width = 430;
  table.columns.get(1).width = 260;
  table.columns.get(2).width = 440;
  table.cells.block({ row: 1, column: 1, rowCount: 2, columnCount: 1 }).textStyle.color = C.red;
  table.cells.block({ row: 4, column: 1, rowCount: 2, columnCount: 1 }).textStyle.color = C.orange;
  table.cells.block({ row: 3, column: 1, rowCount: 1, columnCount: 1 }).textStyle.color = C.amber;
  table.cells.block({ row: 6, column: 1, rowCount: 3, columnCount: 1 }).textStyle.color = C.amber;
  table.cells.block({ row: 9, column: 1, rowCount: 1, columnCount: 1 }).textStyle.color = C.green;
  addFooter(s, "src/quality_rules.py; tests/test_quality_rules.py; tests/fixtures/", 8);
  notes(s, [
    "Je distingue quatre statuts. REJETÉE signale une corruption. EXCLUE PAR RÈGLE MÉTIER décrit une donnée valide qui ne doit pas alimenter le montant.",
    "Le tableau montre la traçabilité : chaque décision non acceptée écrit un code stable et une phrase lisible dans la quarantaine.",
    "Dans les données réellement extraites, aucun rejet qualité n'a été observé. Cela ne signifie pas que les contrôles ne fonctionnent pas : les fixtures artificielles et les tests négatifs déclenchent les rejets attendus sans modifier les résultats publics.",
    "Un taux invalide est retiré des candidats. La vente peut utiliser un taux antérieur encore admissible, sinon elle passe à vérifier.",
  ]);
}

// 9 — preuve exécution
{
  const s = presentation.slides.add();
  addTitle(s, 9, "C3 — Preuve d’exécution du pipeline", "Chaque ligne d’entrée apparaît une fois, soit dans le jeu final, soit dans la quarantaine");
  const chart = s.charts.add("bar", {
    position: { left: 62, top: 158, width: 560, height: 330 },
    categories: ["Acceptées", "À vérifier", "Exclues métier", "Rejetées"],
    series: [{ name: "Lignes", values: [1167, 450, 514, 0], fill: C.cyan, points: [{ idx: 0, fill: C.green }, { idx: 1, fill: C.amber }, { idx: 2, fill: C.orange }, { idx: 3, fill: C.red }] }],
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 45 },
    hasLegend: false,
    xAxis: { min: 0, max: 1300, majorGridlines: { style: "solid", fill: C.line, width: 1 }, textStyle: { fill: C.muted, fontSize: 12 } },
    yAxis: { textStyle: { fill: C.ink, fontSize: 15, bold: true }, line: { fill: C.line, width: 1 } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fill: C.ink, fontSize: 13, bold: true } },
    chartFill: C.paper,
    plotAreaFill: C.paper,
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });
  addText(s, "1 167 + 450 + 514 + 0 = 2 131", 80, 504, 520, 44, { fontSize: 25, bold: true, color: C.navy, alignment: "center" });
  addText(s, "Exemples réels", 675, 154, 500, 32, { fontSize: 18, bold: true, color: C.orange });
  const table = s.tables.add({ rows: 4, columns: 4, left: 675, top: 194, width: 510, height: 225, values: [
    ["item", "décision", "taux", "EUR"],
    ["331", "ACCEPTÉE", "26/01 · 1,0871", "91,94"],
    ["140", "EXCLUE", "—", "—"],
    ["851", "À VÉRIFIER", "—", "—"],
  ] });
  styleTable(table, 4, 4, { fontSize: 13 });
  addText(s, "Contrôles indépendants", 675, 454, 500, 30, { fontSize: 18, bold: true, color: C.orange });
  addText(s, "✓ conservation des volumes\n✓ unicité de la clé finale\n✓ taux âgé de 0 à 7 jours\n✓ conversion EUR ligne par ligne\n✓ séparation des fixtures", 675, 490, 500, 145, { fontSize: 19, color: C.ink });
  addFooter(s, "output/rapport_qualite.json; evidence/rapport_de_tests/c3_output_verification.json", 9);
  notes(s, [
    "Le graphique présente les volumes réellement produits le 16 septembre 2026.",
    "L'exemple 331 part de 99,949996... dans BigQuery, se normalise à 99,95, utilise le taux du vendredi 26 janvier pour la vente du dimanche 28, puis donne 91,94 EUR.",
    "L'item 140 est une annulation valide. L'item 851 reste à vérifier car la commande est en traitement.",
    "Le vérificateur relit les sorties et recalcule la conversion, l'âge du taux, les clés et la partition des lignes.",
  ]);
}

// 10 — résultat métier
{
  const s = presentation.slides.add();
  addTitle(s, 10, "Résultat du POC sur les données publiques", "Le montant en euros reste conditionnel à l’hypothèse non vérifiée que sale_price représente des USD");
  addText(s, "67 052,70 EUR", 72, 170, 520, 92, { fontSize: 48, bold: true, color: C.green, verticalAlignment: "middle" });
  addText(s, "Somme des 1 167 lignes acceptées, après arrondi au centime par ligne", 78, 270, 500, 82, { fontSize: 21, color: C.muted });
  addText(s, "Répartition des 964 lignes hors jeu final", 674, 154, 500, 40, { fontSize: 18, bold: true, color: C.orange });
  const chart = s.charts.add("bar", {
    position: { left: 650, top: 200, width: 530, height: 330 },
    categories: ["Processing", "Cancelled", "Returned"],
    series: [{ name: "Lignes", values: [450, 280, 234], fill: C.orange, points: [{ idx: 0, fill: C.amber }, { idx: 1, fill: C.orange }, { idx: 2, fill: C.navy }] }],
    barOptions: { direction: "column", grouping: "clustered", gapWidth: 55 },
    hasLegend: false,
    xAxis: { textStyle: { fill: C.ink, fontSize: 14, bold: true }, line: { fill: C.line, width: 1 } },
    yAxis: { min: 0, max: 500, majorUnit: 100, majorGridlines: { style: "solid", fill: C.line, width: 1 }, textStyle: { fill: C.muted, fontSize: 12 } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fill: C.ink, fontSize: 14, bold: true } },
    chartFill: C.paper,
    plotAreaFill: C.paper,
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });
  const table = s.tables.add({ rows: 4, columns: 2, left: 80, top: 402, width: 470, height: 180, values: [
    ["Contrôle", "Résultat"],
    ["Clés finales uniques", "1 167 / 1 167"],
    ["Taux ou prix non positif", "0"],
    ["Taux âgé de plus de 7 jours", "0"],
  ] });
  styleTable(table, 4, 2, { fontSize: 15 });
  addText(s, "0 rejet qualité observé dans l’extraction réelle\nLes fixtures séparées prouvent que les règles détectent les anomalies.", 650, 548, 540, 72, { fontSize: 18, bold: true, color: C.green, alignment: "center" });
  addFooter(s, "output/ventes_fiables.csv; output/quarantaine.csv; output/rapport_qualite.json", 10);
  notes(s, [
    "Je formule ce résultat comme une démonstration technique, pas comme un chiffre d'affaires d'entreprise.",
    "La somme vient uniquement des lignes Complete et Shipped qui passent tous les contrôles.",
    "Processing représente les lignes à revoir. Cancelled et Returned sont des exclusions métier, pas des erreurs de qualité.",
    "Le total EUR dépend de l'hypothèse USD. Une validation réelle devrait confirmer la devise et la précision monétaire du système source.",
  ]);
}

// 11 — reproductibilité
{
  const s = presentation.slides.add();
  addTitle(s, 11, "Reproductibilité et CI");
  addText(s, "Reconstruction hors connexion", 72, 154, 500, 34, { fontSize: 18, bold: true, color: C.orange });
  const commands = "python3 src/build_dataset.py\npython3 src/verify_outputs.py\npython3 -m unittest discover -s tests -v";
  addText(s, commands, 72, 198, 550, 138, { fontSize: 18, typeface: MONO, color: "#EAF3F6", fill: C.ink, verticalAlignment: "middle", insets: { left: 18, right: 18, top: 14, bottom: 14 } });
  addText(s, "34 tests réussis", 80, 365, 330, 56, { fontSize: 31, bold: true, color: C.green });
  addText(s, "Cas normaux, négatifs et limites\nIntégration des deux snapshots\nBout en bout, unicité et idempotence", 80, 430, 500, 120, { fontSize: 20, color: C.ink });
  addText(s, "Dépôt public", 700, 154, 470, 34, { fontSize: 18, bold: true, color: C.orange });
  addText(s, "github.com/ljnoam/retail-quality", 700, 202, 470, 50, { fontSize: 24, bold: true, color: C.navy });
  addText(s, "CI GitHub Actions", 700, 290, 470, 34, { fontSize: 18, bold: true, color: C.orange });
  addText(s, "Python 3.13 et 3.14\nDernier run vérifié : succès\nReconstruction et comparaison des fichiers versionnés", 700, 334, 470, 118, { fontSize: 20, color: C.ink });
  addText(s, "SHA-256 des entrées et sorties\nConfiguration sans secrets\nSQL, code, tests et documentation versionnés", 700, 500, 470, 110, { fontSize: 19, color: C.muted });
  addFooter(s, "README.md; .github/workflows/quality.yml; docs/matrice-preuves-rncp.md", 11);
  notes(s, [
    "Le jury peut reproduire C3 sans accès réseau grâce aux snapshots figés et à leurs hashes.",
    "La CI exécute les tests sur deux versions de Python, reconstruit les sorties puis vérifie l'absence de différence avec les fichiers versionnés.",
    "L'idempotence est testée en comparant les fichiers octet par octet après deux exécutions.",
    "Pour refaire C2, le README documente l'authentification BigQuery et le démarrage ou l'installation PostgreSQL. Aucun secret n'est versionné.",
  ]);
}

// 12 — limites
{
  const s = presentation.slides.add();
  addTitle(s, 12, "Limites et validations nécessaires avant un usage réel");
  const rows = [
    ["Données commerciales", "TheLook est fictif et peut évoluer", "Valider sur un extrait d’entreprise gouverné"],
    ["Devise", "sale_price n’expose pas de devise documentée", "Confirmer devise et précision au niveau du système source"],
    ["Règles métier", "Complete et Shipped sont des choix du POC", "Faire valider les statuts par Finance et les métiers"],
    ["Taux de change", "Fenêtre de 7 jours et arrondi par ligne", "Confirmer la politique comptable et la date de conversion"],
    ["Performance", "Volumes BigQuery modestes et 25 taux PostgreSQL", "Mesurer sur le volume cible avant dimensionnement"],
    ["Mise en service", "Prototype local, non déployé chez Thales", "Revoir droits, supervision, sécurité et exploitation"],
  ];
  const table = s.tables.add({ rows: rows.length + 1, columns: 3, left: 66, top: 160, width: 1150, height: 420, values: [["Sujet", "Limite constatée", "Validation requise"], ...rows] });
  styleTable(table, rows.length + 1, 3, { fontSize: 14 });
  table.columns.get(0).width = 220;
  table.columns.get(1).width = 440;
  table.columns.get(2).width = 490;
  addText(s, "Le POC prouve le fonctionnement de la chaîne et sa traçabilité. Il ne prouve ni l’adéquation aux données internes ni la conformité d’une politique comptable réelle.", 94, 606, 1090, 50, { fontSize: 18, bold: true, color: C.navy, alignment: "center" });
  addFooter(s, "docs/sources-et-hypotheses.md; docs/resultats-et-limites.md", 12);
  notes(s, [
    "Je termine en séparant ce que le POC prouve de ce qu'une mise en service exigerait encore.",
    "Le code prouve l'extraction, le rapprochement, les décisions et la reproductibilité sur les données publiques retenues.",
    "Il faut encore confirmer la devise, les statuts comptables, la fenêtre de taux, les droits d'accès et les exigences d'exploitation avec les responsables concernés.",
    "Je rappelle que le projet n'a pas été déployé ou utilisé par Thales.",
  ]);
}

await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const candidatePath = path.join(stagingDir, "retail-quality-soutenance-candidate-corrige.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const requirements = {
  explicitTotalSlideCount: 12,
  requiredNativeTableOwnerSlides: [4, 5, 8, 9, 10, 12],
  requiredNativeChartOwnerSlides: [6, 9, 10],
  requiredEmbeddedWorkbookChartOwnerSlides: [],
  materializeLiteralChartWorkbooks: true,
};

const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-heading-fit",
    ...requirements.requiredNativeTableOwnerSlides.flatMap((number) => ["--require-native-table-slide", String(number)]),
  ],
  fontPolicy: { basis: "design", families: [FONT, MONO] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "retail-quality-soutenance-corrige.validation.json"),
});

console.log(JSON.stringify({ finalPath: FINAL_PPTX, slideCount: 12, validation: result }, null, 2));
