"""Streamlit UI: upload images, OCR locally, structure with AI, export to Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import AIProviderName, Settings, apply_streamlit_secrets_to_environ
from models.document import (
    DocumentProcessingState,
    ExtractionSchema,
    ProcessingStatus,
)
from providers.router import ProviderRouter
from services.excel_service import (
    ExcelExportError,
    export_documents,
    preview_line_item_rows,
    preview_rows,
)
from services.extraction_service import ExtractionService
from ui.pipeline import (
    apply_edits_to_document,
    create_ocr_engine_or_none,
    create_structuring_service,
    get_file_bytes,
    replace_document,
    retry_document,
)
from ui.schema_presets import SCHEMA_PRESETS, get_preset

st.set_page_config(
    page_title="Image-to-Excel Agent",
    page_icon="📄",
    layout="wide",
)

MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def _init_session() -> None:
    if "state" not in st.session_state:
        st.session_state.state = DocumentProcessingState()
    if "file_bytes" not in st.session_state:
        st.session_state.file_bytes: dict[str, bytes] = {}
    if "preset_name" not in st.session_state:
        st.session_state.preset_name = "Pharmacy tax invoice (wholesale)"
    if "provider_choice" not in st.session_state:
        st.session_state.provider_choice = AIProviderName.AUTO.value


def _app_settings() -> Settings:
    """Fresh settings each Streamlit rerun (.env edits need server restart)."""
    apply_streamlit_secrets_to_environ()
    return Settings()


def _session_ocr_engine(settings: Settings):
    """Load PaddleOCR once per session (reload models is slow)."""
    cache_key = f"{settings.ocr_lang}:{settings.paddle_use_gpu}"
    if st.session_state.get("_ocr_cache_key") != cache_key:
        st.session_state.pop("ocr_engine", None)
        st.session_state.pop("ocr_engine_error", None)
        st.session_state._ocr_cache_key = cache_key

    if "ocr_engine" not in st.session_state:
        with st.spinner("Loading PaddleOCR models (first run often takes 1–2 minutes)…"):
            engine, err = create_ocr_engine_or_none(settings)
        if engine is None:
            st.session_state.ocr_engine_error = err
        else:
            st.session_state.ocr_engine = engine
    return st.session_state.get("ocr_engine"), st.session_state.get("ocr_engine_error")


def _session_structuring(settings: Settings, provider_name: AIProviderName):
    cache_key = f"{provider_name.value}:{settings.gemini_model}:{settings.groq_model}"
    if st.session_state.get("_structuring_cache_key") != cache_key:
        st.session_state.pop("structuring_service", None)
        st.session_state._structuring_cache_key = cache_key
    if "structuring_service" not in st.session_state:
        st.session_state.structuring_service = create_structuring_service(
            settings, provider_name
        )
    return st.session_state.structuring_service


def _guess_mime(filename: str) -> str | None:
    ext = Path(filename).suffix.lstrip(".").lower()
    return MIME_BY_EXT.get(ext)


def _provider_label(settings: Settings) -> str:
    configured = settings.configured_cloud_providers()
    if not configured:
        return (
            "None configured — add GEMINI_API_KEY and/or GROQ_API_KEY in `.env` (local) "
            "or Streamlit **Settings → Secrets** (Cloud), then reboot the app."
        )
    return ", ".join(configured)


def _render_sidebar(settings: Settings, schema: ExtractionSchema) -> AIProviderName:
    st.sidebar.header("Configuration")
    st.sidebar.caption("API keys are loaded from `.env` only — never shown here.")
    st.sidebar.markdown(f"**Configured cloud providers:** {_provider_label(settings)}")

    choice = st.sidebar.selectbox(
        "AI provider",
        options=[AIProviderName.AUTO.value, AIProviderName.GEMINI.value, AIProviderName.GROQ.value],
        index=[AIProviderName.AUTO.value, AIProviderName.GEMINI.value, AIProviderName.GROQ.value].index(
            st.session_state.provider_choice
        )
        if st.session_state.provider_choice
        in {AIProviderName.AUTO.value, AIProviderName.GEMINI.value, AIProviderName.GROQ.value}
        else 0,
        help="AUTO uses failover order from AI_PROVIDER_ORDER. OCR always runs locally.",
    )
    st.session_state.provider_choice = choice
    provider_name = AIProviderName(choice)

    st.sidebar.markdown("---")
    preset = st.sidebar.selectbox(
        "Document schema preset",
        options=list(SCHEMA_PRESETS.keys()),
        index=list(SCHEMA_PRESETS.keys()).index(st.session_state.preset_name)
        if st.session_state.preset_name in SCHEMA_PRESETS
        else 0,
    )
    st.session_state.preset_name = preset
    schema = get_preset(preset)
    st.session_state.state.extraction_schema = schema

    st.sidebar.caption(f"Active schema: **{schema.name}** ({len(schema.fields)} fields)")
    st.sidebar.caption(
        f"Models: Gemini `{settings.gemini_model}` · Groq `{settings.groq_model}`"
    )
    st.sidebar.caption("After editing `.env`, restart Streamlit to reload keys/models.")
    if st.sidebar.button("Clear all documents"):
        st.session_state.state = DocumentProcessingState(extraction_schema=schema)
        st.session_state.file_bytes = {}
        st.rerun()

    return provider_name


def _render_provider_health(settings: Settings, provider_name: AIProviderName) -> None:
    try:
        provider = create_structuring_service(settings, provider_name)._provider
    except Exception as exc:
        st.warning(f"AI provider unavailable: {exc}")
        return
    if isinstance(provider, ProviderRouter):
        with st.expander("Provider health (session)"):
            names = [AIProviderName.GEMINI, AIProviderName.GROQ]
            for snap in provider.health.all_snapshots(names):
                status = "available" if snap.available else "cooldown"
                st.write(
                    f"- **{snap.provider.value}**: {status}, "
                    f"failures={snap.consecutive_failures}"
                )
                if snap.last_error:
                    st.caption(snap.last_error)


def _process_uploads(
    settings: Settings,
    schema: ExtractionSchema,
    provider_name: AIProviderName,
    uploads: list,
) -> None:
    ocr_engine, ocr_error = _session_ocr_engine(settings)
    if ocr_engine is None:
        st.error(f"OCR unavailable: {ocr_error}")
        return

    try:
        structuring = _session_structuring(settings, provider_name)
    except Exception as exc:
        st.error(f"AI structuring unavailable: {exc}")
        return

    extraction = ExtractionService(settings, ocr_engine)
    state: DocumentProcessingState = st.session_state.state
    known = state.fingerprint_values()
    progress = st.progress(0.0, text="Starting…")
    total = len(uploads)

    for index, upload in enumerate(uploads):
        content = upload.getvalue()
        mime = upload.type or _guess_mime(upload.name)
        base = index / total

        progress.progress(base + 0.05 / total, text=f"{upload.name}: validating…")
        document = extraction.ingest_upload(
            upload.name,
            content,
            declared_mime=mime,
            known_fingerprints=known,
        )
        if document.status == ProcessingStatus.DUPLICATE_SKIPPED:
            replace_document(state, document)
            st.info(f"{upload.name}: skipped duplicate fingerprint.")
            progress.progress((index + 1) / total, text=f"Done {upload.name}")
            continue

        progress.progress(base + 0.35 / total, text=f"{upload.name}: local OCR…")
        document = extraction.run_ocr(document, content)

        if document.status != ProcessingStatus.OCR_FAILED:
            progress.progress(base + 0.65 / total, text=f"{upload.name}: cloud AI structuring…")
            document = structuring.structure_document(document, schema)

        st.session_state.file_bytes[str(document.id)] = content
        if document.fingerprint is not None:
            known.add(document.fingerprint.value)
        replace_document(state, document)
        if document.error_message:
            st.warning(f"{upload.name}: {document.error_message}")
        progress.progress((index + 1) / total, text=f"Finished {upload.name}")

    progress.empty()
    st.success(f"Finished processing {total} file(s).")


def _status_badge(status: ProcessingStatus) -> str:
    return status.value.replace("_", " ").title()


def _render_document_list(settings: Settings, schema: ExtractionSchema, provider_name: AIProviderName) -> None:
    state: DocumentProcessingState = st.session_state.state
    if not state.documents:
        st.info("Upload images to get started.")
        return

    for doc in state.documents:
        with st.expander(f"{doc.source_filename} — {_status_badge(doc.status)}", expanded=False):
            cols = st.columns([2, 1, 1])
            cols[0].write(f"**Status:** `{doc.status.value}`")
            if doc.last_provider:
                cols[0].caption(f"AI: {doc.last_provider} · OCR: {doc.ocr_engine or '—'}")
            if doc.error_message:
                cols[0].error(doc.error_message)

            if doc.status in (
                ProcessingStatus.OCR_FAILED,
                ProcessingStatus.STRUCTURING_FAILED,
            ):
                if cols[1].button("Retry", key=f"retry-{doc.id}"):
                    content = get_file_bytes(st.session_state.file_bytes, doc.id)
                    if not content:
                        st.warning("Original file bytes not in session; re-upload to retry.")
                    else:
                        ocr_engine, err = _session_ocr_engine(settings)
                        if ocr_engine is None:
                            st.error(err)
                        else:
                            try:
                                structuring = _session_structuring(settings, provider_name)
                            except Exception as exc:
                                st.error(str(exc))
                            else:
                                outcome = retry_document(
                                    settings=settings,
                                    ocr_engine=ocr_engine,
                                    structuring=structuring,
                                    schema=schema,
                                    document=doc.model_copy(deep=True),
                                    content=content,
                                )
                                replace_document(state, outcome.document)
                                st.rerun()

            if doc.extraction is None:
                continue

            edits: dict[str, str | None] = {}
            for field in schema.fields:
                current = doc.extraction.field_map().get(field.key)
                default = current.value if current and current.value is not None else ""
                review = current.review_status.value if current else "missing"
                label = f"{field.label} ({review})"
                edits[field.key] = st.text_input(
                    label,
                    value=default,
                    key=f"edit-{doc.id}-{field.key}",
                )

            if st.button("Save edits", key=f"save-{doc.id}"):
                updated = apply_edits_to_document(doc.model_copy(deep=True), schema, edits)
                replace_document(state, updated)
                st.success("Saved.")
                st.rerun()

            with st.popover("OCR text"):
                st.text(doc.ocr_text or "")


def _render_preview_table(schema: ExtractionSchema) -> None:
    state: DocumentProcessingState = st.session_state.state
    if schema.name == "pharmacy_tax_invoice":
        line_rows = preview_line_item_rows(state.documents)
        if line_rows:
            st.subheader("Product lines (one row per medicine)")
            st.dataframe(pd.DataFrame(line_rows), use_container_width=True, hide_index=True)
            st.divider()
    rows = preview_rows(state.documents, schema)
    if not rows:
        st.caption("No rows ready for preview yet.")
        return
    st.subheader("Invoice summary (one row per image)")
    df = pd.DataFrame(rows)
    show_cols = [
        c
        for c in df.columns
        if c
        in {
            "source_filename",
            "processing_status",
            "export_review_status",
            "schema_name",
        }
        or c in {f.key for f in schema.fields}
        or c.endswith("_review")
    ]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)


def _render_export(settings: Settings, schema: ExtractionSchema) -> None:
    state: DocumentProcessingState = st.session_state.state
    exportable = [
        d
        for d in state.documents
        if d.extraction is not None
        and d.status
        in {
            ProcessingStatus.READY_FOR_EXPORT,
            ProcessingStatus.REVIEW_REQUIRED,
            ProcessingStatus.EXPORTED,
        }
    ]
    st.caption(f"{len(exportable)} document(s) available for export.")

    out_dir = Path("exports")
    out_dir.mkdir(exist_ok=True)
    default_path = out_dir / "extracted_data.xlsx"

    path_str = st.text_input("Excel file path", value=str(default_path))
    mode = st.radio("Export mode", options=["new", "append"], horizontal=True)
    overwrite = st.checkbox("Confirm overwrite existing file (new mode only)", value=False)
    st.caption(
        "Append only works when the path is an existing **.xlsx** file created by this app "
        "(or Excel). If you see a format error, use **new** with overwrite or pick another path."
    )

    if st.button("Export to Excel", type="primary"):
        target = Path(path_str)
        try:
            result = export_documents(
                target,
                state.documents,
                schema,
                settings,
                mode=mode,
                overwrite_confirmed=overwrite,
            )
        except ExcelExportError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Export failed: {exc}")
        else:
            msg = (
                f"Wrote {result.rows_written} summary row(s) to `{result.path}` "
                f"(sheet `{result.sheet_name}`)."
            )
            if result.line_item_rows_written:
                msg += (
                    f" Line items: {result.line_item_rows_written} row(s) "
                    f"on sheet `{result.line_items_sheet_name}`."
                )
            st.success(msg)
            data = target.read_bytes()
            st.download_button(
                "Download workbook",
                data=data,
                file_name=target.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def main() -> None:
    _init_session()
    settings = _app_settings()
    st.title("Image-to-Excel Agent")
    st.markdown(
        "Upload document images · **OCR runs locally** · "
        "Cloud AI receives **OCR text only** · Review · Export to Excel"
    )

    provider_name = _render_sidebar(settings, st.session_state.state.extraction_schema or get_preset("Receipt"))
    schema = st.session_state.state.extraction_schema or get_preset(st.session_state.preset_name)
    st.session_state.state.extraction_schema = schema

    tab_upload, tab_review, tab_export = st.tabs(["Upload & process", "Review & edit", "Export"])

    with tab_upload:
        uploads = st.file_uploader(
            "Images (PNG, JPG, JPEG)",
            type=list(settings.allowed_extensions_set),
            accept_multiple_files=True,
        )
        if uploads and st.button("Run OCR + AI extraction", type="primary"):
            _process_uploads(settings, schema, provider_name, uploads)
        _render_provider_health(settings, provider_name)

    with tab_review:
        _render_preview_table(schema)
        st.divider()
        _render_document_list(settings, schema, provider_name)

    with tab_export:
        _render_export(settings, schema)


if __name__ == "__main__":
    main()
