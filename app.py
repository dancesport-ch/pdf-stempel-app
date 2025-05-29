import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime
import io
import socket
import uuid
import os
import numpy as np
import platform

def get_mac_address():
    """ Holt die vollständige MAC-Adresse für Windows, macOS und Linux """
    mac = uuid.getnode()
    mac_hex = ':'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0, 40, 8)])
    return mac_hex.upper()

def is_area_free(image, x, y, width, height, white_threshold=245, contrast_threshold=15, text_density_threshold=3, min_white_percentage=98):
    """ Überprüft, ob ein Bereich im Bild wirklich frei ist """
    cropped_area = image.crop((x, y, x + width, y + height))
    grayscale = ImageOps.grayscale(cropped_area)  # In Graustufen umwandeln
    pixel_values = np.array(grayscale)

    # Berechnung der Weiß-Anteile & Kontrast
    white_percentage = np.mean(pixel_values > white_threshold) * 100  # Prozent weißer Pixel
    contrast = np.std(pixel_values)  # Standardabweichung als Kontrastmaß
    text_density = np.mean(pixel_values < (white_threshold - 50)) * 100  # Prozent dunkler Pixel als Textdichte

    # Strengste Prüfung: Bereich muss nahezu weiß sein + extrem wenig Kontrast + kaum Textanteile
    return white_percentage >= min_white_percentage and contrast < contrast_threshold and text_density < text_density_threshold

def find_empty_space(page, stamp_width, stamp_height):
    """ Erkennt freie Flächen mit strenger Helligkeits- & Textanalyse von unten nach oben """
    page_rect = page.rect
    pixmap = page.get_pixmap()  # PDF-Seite in Bild umwandeln
    img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

    dpi = 300
    cm_to_pixels = lambda cm: int((cm / 2.54) * dpi)
    step_size = cm_to_pixels(0.25)  # Feineres Raster: 0,25 cm

    for y in range(int(page_rect.height - stamp_height), 0, -step_size):  # Von unten nach oben scannen
        for x in range(0, int(page_rect.width - stamp_width), step_size):
            if is_area_free(img, x, y, stamp_width, stamp_height):
                return x, y

    return page_rect.x0, page_rect.height - stamp_height  # Falls kein Platz gefunden wird, unten links setzen

def create_stamp(name):
    date_time = datetime.today().strftime("%d.%m.%Y %H:%M")  # Datum + Uhrzeit HH:MM
    mac_address = get_mac_address()
    text = f"Geprüft und freigegeben\nDatum: {date_time}\n{name}\nMAC-ID [{mac_address}]"
    dpi = 300
    cm_to_pixels = lambda cm: int((cm / 2.54) * dpi)
    img_width, img_height = cm_to_pixels(1.8), cm_to_pixels(0.8)
    img = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 0))  # Hintergrund auf transparent setzen
    draw = ImageDraw.Draw(img)
    
    # Font-Pfad für verschiedene Betriebssysteme
    font_paths = [
        "C:/Windows/Fonts/calibri.ttf",  # Windows
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
    ]
    
    font_bold = None
    font_regular = None
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                font_bold = ImageFont.truetype(font_path, cm_to_pixels(0.12))
                font_regular = ImageFont.truetype(font_path, cm_to_pixels(0.1))
                break
        except:
            continue
    
    # Fallback auf Standard-Font
    if font_bold is None:
        font_bold = ImageFont.load_default()
        font_regular = ImageFont.load_default()
    
    text_x, text_y = cm_to_pixels(0.1), cm_to_pixels(0.1)
    text_color = (177, 81, 15, 255)
    draw.text((text_x, text_y), "Geprüft und freigegeben", fill=text_color, font=font_bold)
    text_y += font_bold.getbbox("Geprüft und freigegeben")[3] + cm_to_pixels(0.04)
    for line in text.split("\n")[1:]:
        draw.text((text_x, text_y), line, fill=text_color, font=font_regular)
        text_y += font_regular.getbbox(line)[3] + cm_to_pixels(0.04)
    draw.rectangle([(2, 2), (img_width - 2, img_height - 2)], outline=text_color, width=2)
    stamp_io = io.BytesIO()
    img.save(stamp_io, format='PNG')
    return stamp_io.getvalue(), img

def apply_stamp_to_pdf(pdf_bytes, stamp_bytes, x, y, stamp_size):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        page.insert_image(
            fitz.Rect(x, y, x + stamp_size[0], y + stamp_size[1]),
            stream=stamp_bytes,
            overlay=True
        )
    output_pdf = io.BytesIO()
    doc.save(output_pdf)
    return output_pdf.getvalue()

# Streamlit App Konfiguration
st.set_page_config(
    page_title="PDF Stempel Tool",
    page_icon="📄",
    layout="centered"
)

st.title("📄 PDF mit Stempel automatisch versehen")
st.markdown("---")

# Namen-Auswahl
names = ["Martin Zinser", "Brigitte Stäldi", "Oliver Baumann", "Gunar Haas", "Henrik Kattrup", "Nadia Wullschleger", "Walter Vogt"]
name = st.selectbox("1️⃣ Wähle deinen Namen aus:", names)

# PDF Upload
uploaded_file = st.file_uploader("2️⃣ Lade eine PDF hoch", type=["pdf"])

if uploaded_file and name:
    st.success("✅ PDF erfolgreich hochgeladen!")
    
    with st.spinner("🔄 Stempel wird erstellt und angewendet..."):
        try:
            # PDF verarbeiten
            pdf_bytes = uploaded_file.read()
            stamp_bytes, stamp_img = create_stamp(name)
            
            # Freien Platz finden
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[0]
            x, y = find_empty_space(page, stamp_img.size[0], stamp_img.size[1])
            
            st.info(f"ℹ️ Stempel wird automatisch platziert bei: X={x:.0f} px, Y={y:.0f} px")
            
            # Stempel anwenden
            stamped_pdf = apply_stamp_to_pdf(pdf_bytes, stamp_bytes, x, y, stamp_img.size)
            
            # Download-Button
            st.success("✅ PDF erfolgreich gestempelt!")
            
            # Generiere Dateiname
            original_name = uploaded_file.name
            if original_name.lower().endswith('.pdf'):
                new_filename = original_name[:-4] + '_freigegeben.pdf'
            else:
                new_filename = original_name + '_freigegeben.pdf'
            
            st.download_button(
                label="📥 Gestempelte PDF herunterladen",
                data=stamped_pdf,
                file_name=new_filename,
                mime="application/pdf",
                help="Klicken Sie hier, um die gestempelte PDF herunterzuladen"
            )
            
            # Vorschau des Stempels
            st.markdown("---")
            st.subheader("🔍 Stempel-Vorschau:")
            st.image(stamp_img, caption="So sieht Ihr Stempel aus")
            
        except Exception as e:
            st.error(f"❌ Fehler beim Verarbeiten der PDF: {str(e)}")
            st.info("Bitte stellen Sie sicher, dass Sie eine gültige PDF-Datei hochgeladen haben.")

else:
    st.info("👆 Bitte wählen Sie Ihren Namen aus und laden Sie eine PDF-Datei hoch.")

# Footer
st.markdown("---")
st.markdown("**Hinweis:** Diese Anwendung verarbeitet Ihre PDFs lokal und speichert keine Daten.")
