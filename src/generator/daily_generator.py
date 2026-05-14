# src/generator/daily_generator.py
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from src.config import TIMEZONE
from src.utils.datetime_utils import format_for_email, utc_now

logger = logging.getLogger(__name__)

def generate_daily_newsletter(articles: list[dict], edition_number: int) -> dict:
    """
    Generate the daily newsletter HTML and text content.
    """
    now = utc_now()
    date_display = format_for_email(now, TIMEZONE)
    
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )
    
    try:
        template = env.get_template('daily.html')
        html_content = template.render(
            articles=articles,
            date_display=date_display,
            edition_number=edition_number
        )
        
        # Simple text fallback (very basic)
        text_content = f"GridPulse Daily Newsletter - Edition {edition_number}\n"
        text_content += f"{date_display}\n\n"
        for a in articles:
            text_content += f"- {a['title']}\n  {a.get('llm_summary', a['summary'])}\n  {a['url']}\n\n"
            
        return {
            'subject': f"GridPulse Daily Newsletter #{edition_number} - {now.strftime('%Y-%m-%d')}",
            'content_html': html_content,
            'content_text': text_content,
            'article_count': len(articles)
        }
    except Exception as e:
        logger.error(f"Error generating daily newsletter: {e}")
        raise
