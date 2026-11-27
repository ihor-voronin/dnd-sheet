import { Hint } from "../../components/Hint";
import type { SheetDocument, Field as SheetField } from "../../contract/sheetDocument";

function formatValue(field: SheetField): string {
  const value = field.value;
  if (value === null || value === "") return "—";
  if (typeof value === "boolean") return value ? "так" : "ні";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  return String(value);
}

const ORIGIN_LABEL: Record<SheetField["origin"], string> = {
  input: "введено",
  computed: "обчислено",
  override: "вручну",
};

export function SheetView({ document }: { document: SheetDocument }) {
  return (
    <article className="sheet">
      <header className="sheet-header">
        <h1>{document.title.uk}</h1>
        {document.title.en !== document.title.uk ? <p className="original">{document.title.en}</p> : null}
        <p className="meta">Правила 2014 · контракт {document.schemaVersion}</p>
      </header>

      {document.pages.map((page, pageIndex) => (
        <section className="sheet-page" key={`page-${pageIndex}`}>
          {page.sections.map((section) => (
            <div className="sheet-section" key={section.id}>
              <h2>
                {section.title.uk}
                {section.title.en !== section.title.uk ? (
                  <span className="section-original">{section.title.en}</span>
                ) : null}
              </h2>
              <div className="fields" style={{ gridTemplateColumns: `repeat(${section.columns}, minmax(0, 1fr))` }}>
                {section.fields.map((fieldId) => {
                  const field = document.fields[fieldId];
                  if (!field) return null;
                  return (
                    <div className={`field field--${field.type}`} key={fieldId}>
                      <div className="field-label">
                        <span>{field.label.uk}</span>
                        {field.label.en !== field.label.uk ? <Hint original={field.label.en} /> : null}
                      </div>
                      <div className="field-value">{formatValue(field)}</div>
                      {field.hint ? (
                        <div className="field-hint">
                          <span>{field.hint.uk}</span>
                          <Hint original={field.hint.en} />
                        </div>
                      ) : null}
                      <div className={`field-origin field-origin--${field.origin}`}>{ORIGIN_LABEL[field.origin]}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </section>
      ))}
    </article>
  );
}
