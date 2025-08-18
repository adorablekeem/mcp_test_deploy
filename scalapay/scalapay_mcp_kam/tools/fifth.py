from googleapiclient.discovery import Resource
from typing import Any, Dict, List, Optional
from error_handler import handle_google_api_error  # Your custom error handler
from schemas import SummarizePresentationArgs  # Define with 'presentation_id' and 'include_notes'
import json


def extract_text(elements: Optional[List[Dict[str, Any]]]) -> List[str]:
    if not elements:
        return []

    result = []
    for element in elements:
        shape = element.get("shape", {})
        text_elements = shape.get("text", {}).get("textElements", [])
        if text_elements:
            for te in text_elements:
                content = te.get("textRun", {}).get("content", "").strip()
                if content:
                    result.append(content)
        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    cell_text_elements = cell.get("text", {}).get("textElements", [])
                    for te in cell_text_elements:
                        content = te.get("textRun", {}).get("content", "").strip()
                        if content:
                            result.append(content)
    return result


def summarize_presentation_tool(
    slides: Resource,
    args: SummarizePresentationArgs
) -> Dict[str, Any]:
    """
    Extracts text content from all slides in a presentation for summarization.

    Args:
        slides: Authenticated Google Slides API client.
        args: Object with 'presentation_id' and 'include_notes' boolean.

    Returns:
        A dictionary formatted for MCP response.
    """
    include_notes = args.include_notes is True

    try:
        response = slides.presentations().get(
            presentationId=args.presentation_id,
            fields=(
                "presentationId,title,revisionId,"
                "slides(objectId,pageElements(shape(text(textElements(textRun(content)))),"
                "table(tableRows(tableCells(text(textElements(textRun(content))))))),"
                "slideProperties(notesPage(pageElements(shape(text(textElements(textRun(content))))))))"
            )
        ).execute()

        presentation = response
        slides_data = presentation.get("slides", [])

        if not slides_data:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "title": presentation.get("title", "Untitled Presentation"),
                        "slideCount": 0,
                        "summary": "This presentation contains no slides."
                    }, indent=2)
                }]
            }

        slides_content = []
        for idx, slide in enumerate(slides_data):
            slide_number = idx + 1
            slide_id = slide.get("objectId", f"slide_{slide_number}")
            content = " ".join(extract_text(slide.get("pageElements")))

            notes_content = ""
            if include_notes:
                notes_elements = slide.get("slideProperties", {}).get("notesPage", {}).get("pageElements", [])
                notes_content = " ".join(extract_text(notes_elements)).strip()

            slide_summary = {
                "slideNumber": slide_number,
                "slideId": slide_id,
                "content": content
            }
            if include_notes and notes_content:
                slide_summary["notes"] = notes_content

            slides_content.append(slide_summary)

        summary = {
            "title": presentation.get("title", "Untitled Presentation"),
            "slideCount": len(slides_content),
            "lastModified": f"Revision {presentation.get('revisionId')}" if presentation.get("revisionId") else "Unknown",
            "slides": slides_content
        }

        return {
            "content": [{"type": "text", "text": json.dumps(summary, indent=2)}]
        }

    except Exception as error:
        raise handle_google_api_error(error, "summarize_presentation")
