#!/usr/bin/env python3
"""Export all useful AFSer data (Sendees, Hopees, Awayees, Returnees, FWD,
Host Families, Hostees, Profiles, Interviews, Chapters) to Excel workbooks
and CSV files for the private AFS-MUC/Databases repository.
"""

import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / ".private-data/afser.sqlite3"

# Styling constants
AFS_BLUE = "1F4E79"
AFS_LIGHT_BLUE = "D9E1F2"
AFS_ALT_ROW = "F9FAFC"
BORDER_GRAY = "D9D9D9"
WHITE = "FFFFFF"

FONT_NAME = "Arial"

HEADER_FONT = Font(name=FONT_NAME, size=11, bold=True, color=WHITE)
HEADER_FILL = PatternFill(start_color=AFS_BLUE, end_color=AFS_BLUE, fill_type="solid")

TITLE_FONT = Font(name=FONT_NAME, size=16, bold=True, color=AFS_BLUE)
SUBTITLE_FONT = Font(name=FONT_NAME, size=10, italic=True, color="595959")
SECTION_FONT = Font(name=FONT_NAME, size=12, bold=True, color=AFS_BLUE)

CELL_FONT = Font(name=FONT_NAME, size=10)
BOLD_CELL_FONT = Font(name=FONT_NAME, size=10, bold=True)

THIN_BORDER = Border(
    left=Side(style="thin", color=BORDER_GRAY),
    right=Side(style="thin", color=BORDER_GRAY),
    top=Side(style="thin", color=BORDER_GRAY),
    bottom=Side(style="thin", color=BORDER_GRAY),
)

ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


def clean_str(val):
    if val is None:
        return ""
    text = str(val).strip()
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_address(raw):
    if not raw:
        return {"street": "", "postal_code": "", "city": "", "full": ""}
    lines = [re.sub(r"\s+", " ", part.strip()) for part in str(raw).split("<br>") if part.strip()]
    if not lines:
        return {"street": "", "postal_code": "", "city": "", "full": ""}
    full = ", ".join(lines)
    street = lines[0] if len(lines) > 0 else ""
    postal_code = ""
    city = ""
    for line in lines[1:]:
        m = re.search(r"\b(\d{5})\b", line)
        if m:
            postal_code = m.group(1)
            city = line.replace(postal_code, "").strip(" ,-")
            break
    if not city and len(lines) > 1:
        city = lines[-1].strip(" ,-")
    return {"street": street, "postal_code": postal_code, "city": city, "full": full}


def bool_str(val):
    if val is True:
        return "Ja"
    if val is False:
        return "Nein"
    return ""


def load_raw_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Load chapters
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'getAllChapters'")
    chapters = {}
    for (row,) in cur.fetchall():
        d = json.loads(row)
        code = d.get("Chapter_Code__c")
        if code:
            chapters[code] = {
                "id": d.get("Id", ""),
                "name": d.get("Name", ""),
                "region": d.get("Chapter_Region__c", "") or "",
            }

    # Load students
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'getAllStudents'")
    students = [json.loads(row[0]) for row in cur.fetchall()]

    # Load FWD students
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'getAllFwdStudents'")
    fwd_students = [json.loads(row[0]) for row in cur.fetchall()]

    # Load potential host families
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'getHostingPotentialFamilies'")
    potential_families = [json.loads(row[0]) for row in cur.fetchall()]

    # Load host families
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'hostingFamily'")
    hosting_families = [json.loads(row[0]) for row in cur.fetchall()]

    # Load hosted students
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'hostingApplication'")
    hosted_students = [json.loads(row[0]) for row in cur.fetchall()]

    # Load families with students
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'getAllFamiliesWithStudents'")
    families_with_students = [json.loads(row[0]) for row in cur.fetchall()]

    # Load hosting student profiles
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'getAllHostingStudentProfiles'")
    student_profiles = [json.loads(row[0]) for row in cur.fetchall()]

    # Load avt projects
    cur.execute("SELECT payload FROM raw_records WHERE entity_type = 'avtProject'")
    avt_projects = [json.loads(row[0]) for row in cur.fetchall()]

    conn.close()

    return {
        "chapters": chapters,
        "students": students,
        "fwd_students": fwd_students,
        "potential_families": potential_families,
        "hosting_families": hosting_families,
        "hosted_students": hosted_students,
        "families_with_students": families_with_students,
        "student_profiles": student_profiles,
        "avt_projects": avt_projects,
    }


def format_student_row(d, chapters):
    addr = clean_address(d.get("Address__c"))
    chapter_code = (d.get("Chapter__r") or {}).get("Chapter_Code__c", "")
    chapter_info = chapters.get(chapter_code, {})
    chapter_name = chapter_info.get("name", "")
    region = d.get("Region_of_Chapter__c") or chapter_info.get("region", "")

    travel_country = (d.get("Travel_Country__r") or {}).get("Name", "")
    prog_offer = (d.get("Program_Offer__r") or {}).get("Name", "")
    host_fam = (d.get("Assigned_Host_Family__r") or {}).get("Name", "")
    host_addr = clean_str(d.get("Host_Family_Address__c"))

    home_phone = (d.get("Applicant__r") or {}).get("HomePhone", "")
    wahlkreis_nr = (d.get("Wahlkreis__r") or {}).get("Name", "")
    wahlkreis_bez = (d.get("Wahlkreis__r") or {}).get("Wahlkreis_Bez__c", "")

    sem1 = clean_str(d.get("AFS_Seminar_1__c"))
    sem2 = clean_str(d.get("AFS_Seminar_2__c"))
    all_seminars = "Ja" if (sem1 and sem2) else "Nein"

    status = clean_str(d.get("Status__c"))
    if status in ("Application", "Application Plus", "Admission", "Preparation"):
        kategorie = "Hopee (Bewerber)"
    elif status == "Participation":
        kategorie = "Awayee (Aktuell im Ausland)"
    elif status == "Returned":
        kategorie = "Returnee (Zurückgekehrt)"
    elif status == "Termination":
        kategorie = "Beendet / Abbruch"
    else:
        kategorie = status

    return {
        "ID": clean_str(d.get("Id")),
        "Nachname": clean_str(d.get("Last_Name__c")),
        "Vorname": clean_str(d.get("First_Name__c")),
        "Status": status,
        "Status_Kategorie": kategorie,
        "Programmtyp": clean_str(d.get("RecordTypeName__c")),
        "Austauschjahr": clean_str(d.get("Program_Year__c")),
        "Halbkugel": clean_str(d.get("Program_Hemisphere__c")),
        "Programmdauer": clean_str(d.get("Program_Duration__c")),
        "Programmofferte": prog_offer,
        "Zielland": travel_country,
        "Geburtsdatum": clean_str(d.get("Date_of_Birth__c")),
        "EMail": clean_str(d.get("Email_Address__c")),
        "Mobiltelefon": clean_str(d.get("Mobile_Phone__c")),
        "Festnetz": clean_str(home_phone),
        "Strasse": addr["street"],
        "PLZ": addr["postal_code"],
        "Ort": addr["city"],
        "Vollstaendige_Adresse": addr["full"],
        "Komitee_Code": chapter_code,
        "Komitee_Name": chapter_name,
        "Region": region,
        "Schule": clean_str(d.get("Associated_School_Name__c")),
        "Wahlkreis_Nr": clean_str(wahlkreis_nr),
        "Wahlkreis_Name": clean_str(wahlkreis_bez),
        "Eltern_1_EMail": clean_str(d.get("Parent_1c__c")),
        "Eltern_2_EMail": clean_str(d.get("Parent_2c__c")),
        "Homeinterview_Erledigt": bool_str(d.get("HI_Done__c")),
        "AFS_Seminar_1": sem1,
        "AFS_Seminar_2": sem2,
        "Alle_Seminare_Absolviert": all_seminars,
        "Nachbereitung_Seminar": clean_str(d.get("X1_Nachbereitung__c")),
        "Programm_Start": clean_str(d.get("ProgramStartDateDATE__c")),
        "Programm_Ende": clean_str(d.get("ProgramEndDateDATE__c")),
        "Gastfamilie_Ausland_Name": host_fam,
        "Gastfamilie_Ausland_Adresse": host_addr,
        "Doppelbewerbung": bool_str(d.get("Doppelbewerbung__c")),
        "Dossier_PDF_Link": clean_str(d.get("Portal_PDF__c")),
        "Foto_Link": clean_str(d.get("Portal_Photo__c")),
    }


def format_fwd_row(d, chapters):
    addr = clean_address(d.get("Address__c"))
    chapter_code = (d.get("Chapter__r") or {}).get("Chapter_Code__c", "")
    chapter_info = chapters.get(chapter_code, {})
    chapter_name = chapter_info.get("name", "")
    region = d.get("Region_of_Chapter__c") or chapter_info.get("region", "")
    travel_country = (d.get("Travel_Country__r") or {}).get("Name", "")
    prog_offer = (d.get("Program_Offer__r") or {}).get("Name", "")

    status = clean_str(d.get("Status__c"))
    if status in ("Application", "Admission", "Preparation"):
        kategorie = "Hopee (Bewerber)"
    elif status == "Participation":
        kategorie = "Awayee (Aktueller Freiwilliger)"
    elif status == "Returned":
        kategorie = "Returnee (Zurückgekehrt)"
    else:
        kategorie = status

    return {
        "ID": clean_str(d.get("Id")),
        "Nachname": clean_str(d.get("Last_Name__c")),
        "Vorname": clean_str(d.get("First_Name__c")),
        "Status": status,
        "Status_Kategorie": kategorie,
        "Programmjahr": clean_str(d.get("Program_Year__c")),
        "Halbkugel": clean_str(d.get("Program_Hemisphere__c")),
        "Programmdauer": clean_str(d.get("Program_Duration__c")),
        "Programmofferte": prog_offer,
        "Einsatzland": travel_country,
        "Programm_Start": clean_str(d.get("Program_Start_Date__c")),
        "Programm_Ende": clean_str(d.get("Program_End_Date__c")),
        "Geburtsdatum": clean_str(d.get("Date_of_Birth__c")),
        "EMail": clean_str(d.get("Email_Address__c")),
        "Mobiltelefon": clean_str(d.get("Mobile_Phone__c")),
        "Strasse": addr["street"],
        "PLZ": addr["postal_code"],
        "Ort": addr["city"],
        "Vollstaendige_Adresse": addr["full"],
        "Komitee_Code": chapter_code,
        "Komitee_Name": chapter_name,
        "Region": region,
        "Homeinterview_Erledigt": bool_str(d.get("HI_Done__c")),
        "Doppelbewerbung": bool_str(d.get("Doppelbewerbung__c")),
        "Dossier_PDF_Link": clean_str(d.get("Portal_PDF__c")),
        "Foto_Link": clean_str(d.get("Portal_Photo__c")),
    }


def format_potential_family_row(d, chapters):
    addr = clean_address(d.get("Host_Address__c"))
    chapter_code = (d.get("Responsible_Chapter__r") or {}).get("Chapter_Code__c", "")
    chapter_info = chapters.get(chapter_code, {})
    chapter_name = chapter_info.get("name", "")
    region = chapter_info.get("region", "")

    return {
        "ID": clean_str(d.get("Id")),
        "Haushalt_Bezeichnung": clean_str(d.get("Name")),
        "Familienname": clean_str(d.get("Host_Family_Name__c")),
        "Status": clean_str(d.get("Status__c")),
        "Status_Kategorie": "Interessierte Gastfamilie (Hopee)",
        "Komitee_Code": chapter_code,
        "Komitee_Name": chapter_name,
        "Region": region,
        "EMail": clean_str(d.get("E_Mail__c")),
        "Mobiltelefon": clean_str(d.get("Mobile__c")),
        "Festnetz": clean_str(d.get("Home_Phone__c")),
        "Strasse": addr["street"],
        "PLZ": addr["postal_code"],
        "Ort": addr["city"],
        "Vollstaendige_Adresse": addr["full"],
        "Platzierungsart": clean_str(d.get("Placement_Type_AFSer__c")),
        "Gewuenschte_Dauer": clean_str(d.get("Prefered_Program_Duration__c")),
        "Gewuenschte_Halbkugel": clean_str(d.get("Prefered_Program_Hemishere__c")),
        "Gewuenschtes_Jahr": clean_str(d.get("Prefered_Program_Year__c")),
        "Homeinterview_Status": clean_str(d.get("HomeInterview__c")),
    }


def format_hosting_family_row(d, chapters):
    chapter_code = (d.get("Responsible_Chapter__r") or {}).get("Chapter_Code__c", "")
    chapter_info = chapters.get(chapter_code, {})
    chapter_name = chapter_info.get("name", "")
    region = d.get("Responsible_Region__c") or chapter_info.get("region", "")

    buddy = (d.get("AssignedBuddy__r") or {}).get("Full_Name__c", "")
    prog_name = (d.get("Host_Family_Program__r") or {}).get("Name", "")
    primary_contact = clean_str(d.get("Primary_Contact__c"))

    status = clean_str(d.get("Status__c"))
    if status == "Participation":
        kategorie = "Aktive Gastfamilie"
    elif status == "Program End":
        kategorie = "Ehemalige Gastfamilie (Programm beendet)"
    else:
        kategorie = status

    return {
        "ID": clean_str(d.get("Id")),
        "PersID": clean_str(d.get("PersID__c")),
        "Haushalt_Bezeichnung": clean_str(d.get("Name")),
        "Familienname": clean_str(d.get("Host_Family_Name__c")),
        "Status": status,
        "Status_Kategorie": kategorie,
        "Hauptansprechpartner": primary_contact,
        "EMail": clean_str(d.get("E_Mail__c")),
        "Mobiltelefon": clean_str(d.get("Mobile__c")),
        "Festnetz": clean_str(d.get("Home_Phone__c")),
        "Strasse": clean_str(d.get("Street__c")),
        "PLZ": clean_str(d.get("Postal_Code__c")),
        "Ort": clean_str(d.get("City__c")),
        "Bundesland": clean_str(d.get("State__c")),
        "Land": clean_str(d.get("Country__c")),
        "Komitee_Code": chapter_code,
        "Komitee_Name": chapter_name,
        "Region": region,
        "Gastfamilienprogramm": prog_name,
        "Aufnahme_Von": clean_str(d.get("Host_Family_From__c")),
        "Aufnahme_Bis": clean_str(d.get("Host_Family_To__c")),
        "Platzierungsart_AFSer": clean_str(d.get("Placement_Type_AFSer__c")),
        "Platzierungsart_Global": clean_str(d.get("Placement_Type_Global__c")),
        "Betreuer_Buddy": clean_str(buddy),
        "Homeinterview_Status": clean_str(d.get("HomeInterview__c")),
        "Dossier_PDF_Link": clean_str(d.get("Portal_PDF__c")),
    }


def format_hosted_student_row(d):
    country = d.get("Country__c") or (d.get("Travel_Country__r") or {}).get("Name", "")
    buddy = (d.get("Assigned_Buddy__r") or {}).get("Full_Name__c", "")
    prog_offer = (d.get("Program_Offer__r") or {}).get("Name", "")
    birthdate = (d.get("Applicant__r") or {}).get("Birthdate", "")

    start_date = d.get("Program_Start_Date_Overwrite__c") or d.get("Program_Start_Date__c", "")
    end_date = d.get("Program_End_Date_Overwrite__c") or d.get("Program_End_Date__c", "")

    status = clean_str(d.get("Status__c"))
    if status == "Participation":
        kategorie = "Aktiver Gastschüler (Inbound)"
    elif status == "Returned":
        kategorie = "Ehemaliger Gastschüler (Zurückgekehrt)"
    else:
        kategorie = status

    return {
        "ID": clean_str(d.get("Id")),
        "PersID": clean_str(d.get("PersId__c")),
        "Vollstaendiger_Name": clean_str(d.get("Complete_Name__c")),
        "Nachname": clean_str(d.get("Last_Name__c")),
        "Herkunftsland": clean_str(country),
        "Status": status,
        "Status_Kategorie": kategorie,
        "Geburtsdatum": clean_str(birthdate),
        "EMail": clean_str(d.get("Email_Address__c")),
        "Deutsche_Schule": clean_str(d.get("Associated_School_Name__c")),
        "Betreuer_Buddy": clean_str(buddy),
        "Programmofferte": prog_offer,
        "Programmjahr": clean_str(d.get("Program_Year__c")),
        "Halbkugel": clean_str(d.get("Program_Hemisphere__c")),
        "Programmdauer": clean_str(d.get("Program_Duration__c")),
        "Startdatum": clean_str(start_date),
        "Enddatum": clean_str(end_date),
    }


def format_family_placement_row(d, chapters):
    fam = d.get("Hosting_Family__r") or {}
    app = d.get("Application__r") or {}

    chapter_code = (fam.get("Responsible_Chapter__r") or {}).get("Chapter_Code__c", "")
    chapter_info = chapters.get(chapter_code, {})
    chapter_name = chapter_info.get("name", "")
    region = fam.get("Responsible_Region__c") or chapter_info.get("region", "")

    fam_buddy = (fam.get("AssignedBuddy__r") or {}).get("Full_Name__c", "")
    student_buddy = (app.get("Assigned_Buddy__r") or {}).get("Full_Name__c", "")
    prog_offer = (app.get("Program_Offer__r") or {}).get("Name", "")
    country = app.get("Country__c") or (app.get("Travel_Country__r") or {}).get("Name", "")
    birthdate = (app.get("Applicant__r") or {}).get("Birthdate", "")

    fam_status = clean_str(fam.get("Status__c"))
    student_status = clean_str(app.get("Status__c"))

    return {
        "Platzierung_Status": clean_str(d.get("Status_Global__c")),
        "Familie_ID": clean_str(fam.get("Id")),
        "Haushalt_Name": clean_str(fam.get("Name")),
        "Familienname": clean_str(fam.get("Host_Family_Name__c")),
        "Familie_Status": fam_status,
        "Familie_EMail": clean_str(fam.get("E_Mail__c")),
        "Familie_Mobil": clean_str(fam.get("Mobile__c")),
        "Familie_Festnetz": clean_str(fam.get("Home_Phone__c")),
        "Familie_Strasse": clean_str(fam.get("Street__c")),
        "Familie_PLZ": clean_str(fam.get("Postal_Code__c")),
        "Familie_Ort": clean_str(fam.get("City__c")),
        "Familie_Bundesland": clean_str(fam.get("State__c")),
        "Komitee_Code": chapter_code,
        "Komitee_Name": chapter_name,
        "Region": region,
        "Aufnahme_Von": clean_str(fam.get("Host_Family_From__c")),
        "Aufnahme_Bis": clean_str(fam.get("Host_Family_To__c")),
        "Familien_Betreuer": clean_str(fam_buddy),
        "Gastschueler_ID": clean_str(app.get("Id")),
        "Gastschueler_Name": clean_str(app.get("Complete_Name__c")),
        "Gastschueler_Herkunftsland": clean_str(country),
        "Gastschueler_Geburtsdatum": clean_str(birthdate),
        "Gastschueler_Status": student_status,
        "Gastschueler_EMail": clean_str(app.get("Email_Address__c")),
        "Gastschueler_Schule": clean_str(app.get("Associated_School_Name__c")),
        "Gastschueler_Betreuer": clean_str(student_buddy),
        "Programmofferte": prog_offer,
        "Programmjahr": clean_str(app.get("Program_Year__c")),
        "Programmdauer": clean_str(app.get("Program_Duration__c")),
    }


def format_student_profile_row(d):
    app = d.get("Application__r") or {}
    prog_offer = app.get("Program_Offer__r") or {}
    country = app.get("Country__c") or (app.get("Travel_Country__r") or {}).get("Name", "")

    return {
        "Profil_ID": clean_str(d.get("Id")),
        "Bewerbung_ID": clean_str(app.get("Id")),
        "PersID": clean_str(app.get("PersId__c")),
        "Vorname": clean_str(app.get("First_Name__c")),
        "Nachname": clean_str(app.get("Last_Name__c")),
        "Herkunftsland": clean_str(country),
        "Geschlecht": clean_str(app.get("Gender__c")),
        "Geburtsdatum": clean_str(app.get("Date_of_Birth__c")),
        "Status_Platzierung": clean_str(d.get("Status_der_Platzierung__c")),
        "Reservierung_Status": clean_str(d.get("Reservierung__c")),
        "Offen_fuer_Platzierung": clean_str(d.get("Offen_fr_Platzierung__c")),
        "Programmjahr": clean_str(app.get("Program_Year__c")),
        "Halbkugel": clean_str(app.get("Program_Hemisphere__c")),
        "Programmdauer": clean_str(app.get("Program_Duration__c")),
        "Ankunft_Datum": clean_str(prog_offer.get("From_Arrival_Date__c")),
        "Abreise_Datum": clean_str(prog_offer.get("From_Departure_Date__c")),
        "Sport": clean_str(d.get("Sport__c")),
        "Interessen": clean_str(d.get("Interessen__c")),
        "Sprachen": clean_str(d.get("Sprachen__c")),
        "Geschwister": clean_str(d.get("Geschwister__c")),
        "Religion": clean_str(d.get("Religion__c")),
        "Essenseinschraenkungen": clean_str(d.get("Essenseinschrnkungen__c")),
        "Essenseinschraenkungen_Details": clean_str(d.get("Essenseinschrnkungen_Text__c")),
        "Platzierungsrelevante_Aspekte": clean_str(d.get("Platzierungsrelevante_Aspekte__c")),
        "Platzierungsrelevante_Details": clean_str(d.get("Platzierungsrelevante_Aspekte_Text__c")),
        "Stipendium_Anmerkung": clean_str(d.get("Anmerkungen_Platzierung__c")),
        "Online_seit": clean_str(d.get("Datum_Online_AFSer_de__c")),
        "Kurztext_Vorstellung": clean_str(d.get("Kurztext__c")),
    }


def format_avt_project_row(d, chapters):
    chapter_code = clean_str(d.get("chapter"))
    chapter_info = chapters.get(chapter_code, {})
    chapter_name = chapter_info.get("name", "")
    region = chapter_info.get("region", "")

    date_text = clean_str(d.get("dateText"))
    start_date = ""
    end_date = ""
    if "-" in date_text:
        parts = [p.strip() for p in date_text.split("-") if p.strip()]
        if len(parts) >= 2:
            start_date, end_date = parts[0], parts[1]
        elif len(parts) == 1:
            start_date = parts[0]

    available_roles = d.get("availableInterviewRoles")
    assigned_roles = d.get("assignedInterviewRoles")

    avail_count = len(available_roles) if isinstance(available_roles, list) else 0
    assigned_count = int(assigned_roles) if assigned_roles is not None else 0

    if avail_count > 0:
        slot_status = "Offen (Freie Plätze)"
    elif assigned_count > 0:
        slot_status = "Vollständig vergeben"
    else:
        slot_status = "Unbekannt / Kein Slot"

    return {
        "Projekt_ID": clean_str(d.get("Id")),
        "Titel": clean_str(d.get("title")),
        "Programm": clean_str(d.get("program")),
        "Komitee_Code": chapter_code,
        "Komitee_Name": chapter_name,
        "Region": region,
        "Status_Slots": slot_status,
        "Freie_Rollen_Anzahl": avail_count,
        "Vergebene_Rollen_Anzahl": assigned_count,
        "Zeitraum_Text": date_text,
        "Startdatum": start_date,
        "Enddatum_Frist": end_date,
        "Prioritaet": clean_str(d.get("priority")),
        "Zustaendiges_Team": clean_str(d.get("team")),
        "AFSer_URL": clean_str(d.get("sourceUrl")),
    }


def add_styled_sheet(wb, title, headers, rows):
    ws = wb.create_sheet(title=title[:31])

    # Header row
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER

    # Data rows
    for row_idx, row_data in enumerate(rows, start=2):
        ws.append([row_data.get(h, "") for h in headers])
        is_alt = (row_idx % 2 == 1)
        row_fill = PatternFill(start_color=AFS_ALT_ROW, end_color=AFS_ALT_ROW, fill_type="solid") if is_alt else None

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = CELL_FONT
            cell.border = THIN_BORDER
            if row_fill:
                cell.fill = row_fill

            # Alignments
            val_str = str(cell.value or "")
            if header in ("ID", "Komitee_Code", "Status", "Status_Kategorie", "Halbkugel", "Programmdauer",
                          "Austauschjahr", "Programmjahr", "Geburtsdatum", "Programm_Start", "Programm_Ende",
                          "Startdatum", "Enddatum", "Homeinterview_Erledigt", "Alle_Seminare_Absolviert",
                          "Freie_Rollen_Anzahl", "Vergebene_Rollen_Anzahl", "PLZ"):
                cell.alignment = ALIGN_CENTER
            elif header.startswith("http") or header.endswith("_Link") or header.endswith("_URL"):
                cell.alignment = ALIGN_LEFT
            else:
                cell.alignment = ALIGN_LEFT

    # Freeze panes
    ws.freeze_panes = "A2"

    # Set auto-filter
    if rows:
        ws.auto_filter.ref = ws.dimensions

    # Adjust column widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col[:100]:  # sample up to 100 rows for speed
            val = str(cell.value or "")
            if len(val) > max_len:
                max_len = len(val)
        # bound between 10 and 50
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)

    return ws


def write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({h: r.get(h, "") for h in headers})


def create_overview_sheet(wb, stats):
    ws = wb.active
    ws.title = "Übersicht & Statistik"

    ws.views.sheetView[0].showGridLines = True

    # Title block
    ws["B2"] = "AFS Interkulturelle Begegnungen e.V."
    ws["B2"].font = TITLE_FONT
    ws["B3"] = f"AFSer Datenexport – Vollständige Tabellenübersicht (Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')})"
    ws["B3"].font = SUBTITLE_FONT

    ws["B5"] = "Zusammenfassung der Datensätze"
    ws["B5"].font = SECTION_FONT

    summary_headers = ["Kategorie / Bereich", "Anzahl Datensätze", "Beschreibung"]
    ws.append([])  # 6
    ws.append([])  # 7
    row_start = 7

    for col_idx, h in enumerate(summary_headers, start=2):
        cell = ws.cell(row=row_start, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER

    summary_data = [
        ("1. Hopees (Bewerber Schüleraustausch)", stats["hopees_count"], "Bewerbungen in Phasen Application, Application Plus, Admission, Preparation"),
        ("2. Awayees (Aktuell im Ausland)", stats["awayees_count"], "Schülerinnen und Schüler aktuell im Auslandsprogramm (Participation)"),
        ("3. Returnees (Zurückgekehrt)", stats["returnees_count"], "Ehemalige Austauschschüler nach Abschluss des Programms (Returned)"),
        ("4. Sendees Gesamt (Schüleraustausch)", stats["students_count"], "Gesamter Datenbestand inklusive Abbrüche (Termination) und Historie"),
        ("5. FWD Freiwilligendienst", stats["fwd_count"], "Freiwilligendienst-Teilnehmende (Bewerber, Aktive im Ausland, Returnees)"),
        ("6. Gastfamilien Interessierte (Hopees)", stats["potential_families_count"], "Familien in Bewerbung oder Aufnahmephase zur Aufnahme eines Gastschülers"),
        ("7. Gastfamilien Aktiv & Historie", stats["hosting_families_count"], "Gastfamilien im Programm (28 aktiv, 34 Programm beendet)"),
        ("8. Hostees (Inbound Gastschüler)", stats["hosted_students_count"], "Internationale Gastschüler in Deutschland (28 aktiv, 32 zurückgekehrt)"),
        ("9. Gastfamilien-Platzierungen", stats["placements_count"], "Verknüpfte Zuweisungen von Gastfamilien und Gastschülern"),
        ("10. Gastkinder-Suchprofile (Q-Bogen)", stats["profiles_count"], "Detaillierte Schülerprofile für Familien- & Wechselfamiliensuche"),
        ("11. Homeinterviews (AVT-Board)", stats["avt_projects_count"], "Homeinterview-Projekte auf dem AVT-Board (Sending & Hosting)"),
        ("12. AFS Komitees & Regionen", stats["chapters_count"], "Alle 95 Komitees in Deutschland mit Regionalzuordnung"),
    ]

    for offset, (cat, cnt, desc) in enumerate(summary_data, start=1):
        r = row_start + offset
        c1 = ws.cell(row=r, column=2, value=cat)
        c2 = ws.cell(row=r, column=3, value=cnt)
        c3 = ws.cell(row=r, column=4, value=desc)

        for c in (c1, c2, c3):
            c.font = CELL_FONT
            c.border = THIN_BORDER
        c1.font = BOLD_CELL_FONT
        c2.alignment = ALIGN_RIGHT
        c3.alignment = ALIGN_LEFT

    # Breakdown by sending status
    r_breakdown = row_start + len(summary_data) + 2
    ws.cell(row=r_breakdown, column=2, value="Status-Aufschlüsselung Schüleraustausch (Sending)").font = SECTION_FONT

    status_headers = ["Status", "Anzahl", "Kategorie"]
    r_sh = r_breakdown + 1
    for col_idx, h in enumerate(status_headers, start=2):
        cell = ws.cell(row=r_sh, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER

    for offset, (st, cnt, kat) in enumerate(stats["status_breakdown"], start=1):
        r = r_sh + offset
        c1 = ws.cell(row=r, column=2, value=st)
        c2 = ws.cell(row=r, column=3, value=cnt)
        c3 = ws.cell(row=r, column=4, value=kat)
        for c in (c1, c2, c3):
            c.font = CELL_FONT
            c.border = THIN_BORDER
        c2.alignment = ALIGN_RIGHT

    # Column dimensions for overview
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 42
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 80


def export_all(target_repo_dir):
    print("Loading raw data from database...")
    data = load_raw_data()
    chapters = data["chapters"]

    print("Formatting student records...")
    formatted_students = [format_student_row(s, chapters) for s in data["students"]]
    hopees_rows = [s for s in formatted_students if s["Status"] in ("Application", "Application Plus", "Admission", "Preparation")]
    awayees_rows = [s for s in formatted_students if s["Status"] == "Participation"]
    returnees_rows = [s for s in formatted_students if s["Status"] == "Returned"]

    print("Formatting FWD records...")
    formatted_fwd = [format_fwd_row(s, chapters) for s in data["fwd_students"]]
    fwd_hopees = [s for s in formatted_fwd if s["Status"] in ("Application", "Admission", "Preparation")]
    fwd_awayees = [s for s in formatted_fwd if s["Status"] == "Participation"]
    fwd_returnees = [s for s in formatted_fwd if s["Status"] == "Returned"]

    print("Formatting hosting records...")
    formatted_potential_fam = [format_potential_family_row(f, chapters) for f in data["potential_families"]]
    formatted_hosting_fam = [format_hosting_family_row(f, chapters) for f in data["hosting_families"]]
    fam_active = [f for f in formatted_hosting_fam if f["Status"] == "Participation"]
    fam_ended = [f for f in formatted_hosting_fam if f["Status"] == "Program End"]

    formatted_hosted_students = [format_hosted_student_row(s) for s in data["hosted_students"]]
    formatted_placements = [format_family_placement_row(p, chapters) for p in data["families_with_students"]]
    formatted_profiles = [format_student_profile_row(p) for p in data["student_profiles"]]

    print("Formatting interview records...")
    formatted_avt = [format_avt_project_row(p, chapters) for p in data["avt_projects"]]
    avt_open = [p for p in formatted_avt if p["Freie_Rollen_Anzahl"] > 0]
    avt_assigned = [p for p in formatted_avt if p["Freie_Rollen_Anzahl"] == 0]

    print("Formatting chapter records...")
    chapter_rows = []
    for code, info in sorted(chapters.items()):
        chapter_rows.append({
            "Komitee_Code": code,
            "Komitee_Name": info.get("name", ""),
            "Region": info.get("region", ""),
            "Salesforce_ID": info.get("id", ""),
        })

    # Prepare stats
    from collections import Counter
    status_counts = Counter(s["Status"] for s in formatted_students)
    status_breakdown = []
    for st, count in status_counts.most_common():
        if st in ("Application", "Application Plus", "Admission", "Preparation"):
            kat = "Hopee (Bewerber)"
        elif st == "Participation":
            kat = "Awayee (Aktuell im Ausland)"
        elif st == "Returned":
            kat = "Returnee (Zurückgekehrt)"
        elif st == "Termination":
            kat = "Beendet / Abbruch"
        else:
            kat = st
        status_breakdown.append((st, count, kat))

    stats = {
        "hopees_count": len(hopees_rows),
        "awayees_count": len(awayees_rows),
        "returnees_count": len(returnees_rows),
        "students_count": len(formatted_students),
        "fwd_count": len(formatted_fwd),
        "potential_families_count": len(formatted_potential_fam),
        "hosting_families_count": len(formatted_hosting_fam),
        "hosted_students_count": len(formatted_hosted_students),
        "placements_count": len(formatted_placements),
        "profiles_count": len(formatted_profiles),
        "avt_projects_count": len(formatted_avt),
        "chapters_count": len(chapter_rows),
        "status_breakdown": status_breakdown,
    }

    # Define headers
    student_headers = list(formatted_students[0].keys())
    fwd_headers = list(formatted_fwd[0].keys())
    potential_fam_headers = list(formatted_potential_fam[0].keys())
    hosting_fam_headers = list(formatted_hosting_fam[0].keys())
    hosted_student_headers = list(formatted_hosted_students[0].keys())
    placement_headers = list(formatted_placements[0].keys())
    profile_headers = list(formatted_profiles[0].keys())
    avt_headers = list(formatted_avt[0].keys())
    chapter_headers = ["Komitee_Code", "Komitee_Name", "Region", "Salesforce_ID"]

    target_dir = Path(target_repo_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. MASTER WORKBOOK: AFS_Gesamtdaten_Alle_Bereiche.xlsx
    # =========================================================================
    print("Generating Master Workbook: AFS_Gesamtdaten_Alle_Bereiche.xlsx ...")
    wb_master = openpyxl.Workbook()
    create_overview_sheet(wb_master, stats)
    add_styled_sheet(wb_master, "Hopees (Bewerber Sending)", student_headers, hopees_rows)
    add_styled_sheet(wb_master, "Awayees (Aktuell im Ausland)", student_headers, awayees_rows)
    add_styled_sheet(wb_master, "Returnees (Zurückgekehrt)", student_headers, returnees_rows)
    add_styled_sheet(wb_master, "Alle Sendees (1940 Datensätze)", student_headers, formatted_students)
    add_styled_sheet(wb_master, "FWD Freiwilligendienst", fwd_headers, formatted_fwd)
    add_styled_sheet(wb_master, "Gastfamilien Interessierte", potential_fam_headers, formatted_potential_fam)
    add_styled_sheet(wb_master, "Gastfamilien Aktiv & Past", hosting_fam_headers, formatted_hosting_fam)
    add_styled_sheet(wb_master, "Hostees Inbound Gastschüler", hosted_student_headers, formatted_hosted_students)
    add_styled_sheet(wb_master, "Gastfamilien-Platzierungen", placement_headers, formatted_placements)
    add_styled_sheet(wb_master, "Gastkinder Suchprofile", profile_headers, formatted_profiles)
    add_styled_sheet(wb_master, "Homeinterviews AVT-Board", avt_headers, formatted_avt)
    add_styled_sheet(wb_master, "AFS Komitees & Regionen", chapter_headers, chapter_rows)

    master_path = target_dir / "AFS_Gesamtdaten_Alle_Bereiche.xlsx"
    wb_master.save(master_path)
    print(f"Saved master workbook to {master_path}")

    # =========================================================================
    # 2. DEDICATED WORKBOOK: 1_Sending_und_Hopees.xlsx
    # =========================================================================
    print("Generating 1_Sending_und_Hopees.xlsx ...")
    wb_send = openpyxl.Workbook()
    ws_send_default = wb_send.active
    wb_send.remove(ws_send_default)
    add_styled_sheet(wb_send, "Hopees (Bewerber)", student_headers, hopees_rows)
    add_styled_sheet(wb_send, "Awayees (Im Ausland)", student_headers, awayees_rows)
    add_styled_sheet(wb_send, "Returnees (Zurückgekehrt)", student_headers, returnees_rows)
    add_styled_sheet(wb_send, "Alle Sendees", student_headers, formatted_students)
    wb_send.save(target_dir / "1_Sending_und_Hopees.xlsx")

    # =========================================================================
    # 3. DEDICATED WORKBOOK: 2_FWD_Freiwilligendienst.xlsx
    # =========================================================================
    print("Generating 2_FWD_Freiwilligendienst.xlsx ...")
    wb_fwd = openpyxl.Workbook()
    ws_fwd_default = wb_fwd.active
    wb_fwd.remove(ws_fwd_default)
    add_styled_sheet(wb_fwd, "FWD Bewerber (Hopees)", fwd_headers, fwd_hopees)
    add_styled_sheet(wb_fwd, "FWD Aktive (Awayees)", fwd_headers, fwd_awayees)
    add_styled_sheet(wb_fwd, "FWD Returnees", fwd_headers, fwd_returnees)
    add_styled_sheet(wb_fwd, "Alle FWD Teilnehmende", fwd_headers, formatted_fwd)
    wb_fwd.save(target_dir / "2_FWD_Freiwilligendienst.xlsx")

    # =========================================================================
    # 4. DEDICATED WORKBOOK: 3_Hosting_Gastfamilien_und_Hostees.xlsx
    # =========================================================================
    print("Generating 3_Hosting_Gastfamilien_und_Hostees.xlsx ...")
    wb_host = openpyxl.Workbook()
    ws_host_default = wb_host.active
    wb_host.remove(ws_host_default)
    add_styled_sheet(wb_host, "Interessierte Familien (Hopees)", potential_fam_headers, formatted_potential_fam)
    add_styled_sheet(wb_host, "Aktive Gastfamilien", hosting_fam_headers, fam_active)
    add_styled_sheet(wb_host, "Gastfamilien Historie", hosting_fam_headers, fam_ended)
    add_styled_sheet(wb_host, "Inbound Gastschüler", hosted_student_headers, formatted_hosted_students)
    add_styled_sheet(wb_host, "Platzierungen", placement_headers, formatted_placements)
    add_styled_sheet(wb_host, "Gastkinder Suchprofile (Q-Bogen)", profile_headers, formatted_profiles)
    wb_host.save(target_dir / "3_Hosting_Gastfamilien_und_Hostees.xlsx")

    # =========================================================================
    # 5. DEDICATED WORKBOOK: 4_Homeinterviews_AVT_Board.xlsx
    # =========================================================================
    print("Generating 4_Homeinterviews_AVT_Board.xlsx ...")
    wb_avt = openpyxl.Workbook()
    ws_avt_default = wb_avt.active
    wb_avt.remove(ws_avt_default)
    add_styled_sheet(wb_avt, "Offene Interviews (Freie Slots)", avt_headers, avt_open)
    add_styled_sheet(wb_avt, "Vergebene Interviews", avt_headers, avt_assigned)
    add_styled_sheet(wb_avt, "Alle Interviewprojekte", avt_headers, formatted_avt)
    wb_avt.save(target_dir / "4_Homeinterviews_AVT_Board.xlsx")

    # =========================================================================
    # 6. DEDICATED WORKBOOK: 5_AFS_Komitees_und_Regionen.xlsx
    # =========================================================================
    print("Generating 5_AFS_Komitees_und_Regionen.xlsx ...")
    wb_ch = openpyxl.Workbook()
    ws_ch_default = wb_ch.active
    wb_ch.remove(ws_ch_default)
    add_styled_sheet(wb_ch, "Komitees Deutschland", chapter_headers, chapter_rows)
    wb_ch.save(target_dir / "5_AFS_Komitees_und_Regionen.xlsx")

    # =========================================================================
    # 7. CSV EXPORTS
    # =========================================================================
    print("Writing CSV files...")
    csv_dir = target_dir / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    write_csv(csv_dir / "sendees_hopees_bewerber.csv", student_headers, hopees_rows)
    write_csv(csv_dir / "sendees_awayees_im_ausland.csv", student_headers, awayees_rows)
    write_csv(csv_dir / "sendees_returnees.csv", student_headers, returnees_rows)
    write_csv(csv_dir / "sendees_alle_schueleraustausch.csv", student_headers, formatted_students)
    write_csv(csv_dir / "fwd_freiwilligendienst_alle.csv", fwd_headers, formatted_fwd)
    write_csv(csv_dir / "gastfamilien_interessierte_hopees.csv", potential_fam_headers, formatted_potential_fam)
    write_csv(csv_dir / "gastfamilien_aktiv_und_past.csv", hosting_fam_headers, formatted_hosting_fam)
    write_csv(csv_dir / "hostees_inbound_gastschueler.csv", hosted_student_headers, formatted_hosted_students)
    write_csv(csv_dir / "gastfamilien_platzierungen.csv", placement_headers, formatted_placements)
    write_csv(csv_dir / "gastkinder_suchprofile_q_bogen.csv", profile_headers, formatted_profiles)
    write_csv(csv_dir / "homeinterviews_avt_board.csv", avt_headers, formatted_avt)
    write_csv(csv_dir / "afs_komitees_deutschland.csv", chapter_headers, chapter_rows)

    # =========================================================================
    # 8. README.md
    # =========================================================================
    print("Writing README.md ...")
    readme_content = f"""# AFS Interkulturelle Begegnungen e.V. – Interner Datenexport

Dieses private Repository enthält alle relevanten Datensätze aus dem AFSer-System in professionell aufbereiteten Excel-Arbeitsmappen (`.xlsx`) sowie maschinenlesbaren CSV-Dateien (`csv/`).

**Datenstand:** {datetime.now().strftime('%d.%m.%Y %H:%M Uhr')}  
**Quelle:** AFSer.de interner Datenbestand (`afser.sqlite3`)

---

## 📊 Datensatz-Übersicht & Statistiken

| Datensatz / Tabelle | Anzahl Zeilen | Status / Phasen | Beschreibung |
|---|---:|---|---|
| **Hopees (Bewerber Sending)** | **{stats['hopees_count']}** | `Application`, `Application Plus`, `Admission`, `Preparation` | Bewerbende für das Schüleraustauschprogramm (aktueller Zyklus) mit Kontaktdaten, Elternkontakten, Wahlkreis & Seminaren |
| **Awayees (Aktuell im Ausland)** | **{stats['awayees_count']}** | `Participation` | Schülerinnen und Schüler, die aktuell im Gastland leben, inklusive Gastfamilie vor Ort |
| **Returnees (Zurückgekehrt)** | **{stats['returnees_count']}** | `Returned` | Zurückgekehrte Austauschschüler mit Seminar- & Nachbereitungsstatus |
| **Sendees Gesamt** | **{stats['students_count']}** | Alle Status (`Termination`, `Returned`, `Participation`, etc.) | Vollständiger Gesamtdatensatz aller 1.940 Schüleraustausch-Bewerbungen |
| **FWD Freiwilligendienst** | **{stats['fwd_count']}** | Bewerber ({len(fwd_hopees)}), Aktive ({len(fwd_awayees)}), Returnees ({len(fwd_returnees)}) | Freiwilligendienstler im Ausland (Weltwärts / Internationaler Jugendfreiwilligendienst) |
| **Gastfamilien Interessierte (Hopees)** | **{stats['potential_families_count']}** | `Admission`, `Application` | Potenzielle Gastfamilien in Aufnahme- und Prüfungsphase mit Präferenzen & Adressen |
| **Gastfamilien Aktiv & Historie** | **{stats['hosting_families_count']}** | `Participation` ({len(fam_active)}), `Program End` ({len(fam_ended)}) | Vollständige Gastfamiliendaten mit Kontaktdaten, Buddy, Adressen und Programmzuordnung |
| **Hostees (Inbound Gastschüler)** | **{stats['hosted_students_count']}** | `Participation` (28), `Returned` (32) | Internationale Austauschschüler in Deutschland mit Schule, Betreuer und Herkunftsland |
| **Gastfamilien-Platzierungen** | **{stats['placements_count']}** | Verknüpft | 1-zu-1-Zuordnungen zwischen Gastfamilien und ihren platzierten Gastschülern |
| **Gastkinder-Suchprofile (Q-Bogen)** | **{stats['profiles_count']}** | `Familie gesucht`, `Wechselfamilie gesucht` | Detaillierte Profile internationaler Schüler (Vorstellungstext, Hobbies, Sprachen, Ernährung) |
| **Homeinterviews (AVT-Board)** | **{stats['avt_projects_count']}** | Offen ({len(avt_open)}), Vergeben ({len(avt_assigned)}) | Homeinterview-Aufträge und Fristen aus dem AVT-Board für Sending und Hosting |
| **AFS Komitees & Regionen** | **{stats['chapters_count']}** | Deutschlandweit | Alle 95 AFS-Komitees mit 3-Buchstaben-Code, Klarnamen und Region (Süd, West, Nord, Ost, Mitte) |

---

## 📁 Dateistruktur

```text
.
├── AFS_Gesamtdaten_Alle_Bereiche.xlsx       # Master-Arbeitsmappe mit allen 12 Tabellen & Dashboard
├── 1_Sending_und_Hopees.xlsx               # Arbeitsmappe für das Sending-Team (Hopees, Awayees, Returnees)
├── 2_FWD_Freiwilligendienst.xlsx           # Arbeitsmappe für das FWD-Team
├── 3_Hosting_Gastfamilien_und_Hostees.xlsx # Arbeitsmappe für das Hosting-Team (Familien, Hostees, Profile)
├── 4_Homeinterviews_AVT_Board.xlsx         # Arbeitsmappe für Interview-Koordination & freie Slots
├── 5_AFS_Komitees_und_Regionen.xlsx        # Referenztabelle aller Komitees und Regionen
└── csv/                                    # Reine CSV-Dateien für Programmierung / Datenbanken
    ├── sendees_hopees_bewerber.csv
    ├── sendees_awayees_im_ausland.csv
    ├── sendees_returnees.csv
    ├── sendees_alle_schueleraustausch.csv
    ├── fwd_freiwilligendienst_alle.csv
    ├── gastfamilien_interessierte_hopees.csv
    ├── gastfamilien_aktiv_und_past.csv
    ├── hostees_inbound_gastschueler.csv
    ├── gastfamilien_platzierungen.csv
    ├── gastkinder_suchprofile_q_bogen.csv
    ├── homeinterviews_avt_board.csv
    └── afs_komitees_deutschland.csv
```

---

## 🛠 Features der Excel-Dateien
- **Professionelles Corporate Design:** AFS-Dunkelblaues Header-Styling (`#1F4E79`), weiße Fettschrift, saubere Rahmen.
- **Benutzerfreundliche Bedienung:** 
  - Erste Zeile fixiert (*Freeze Panes*), damit Spaltenüberschriften beim Scrollen stets sichtbar bleiben.
  - Auto-Filter auf allen Tabellen aktiviert zum schnellen Sortieren und Filtern nach Komitee, Land, Status etc.
  - Spaltenbreiten automatisch auf den Inhalt optimiert.
  - Adressen sauber getrennt in Straße, Postleitzahl und Ort.
  - Telefonnummern, E-Mails, Dossier-PDF-Links und Fotos direkt anklickbar bzw. filterbar.
- **Datenschutz:** Dieses Repository ist privat. Es enthält personenbezogene Teilnehmer- und Kontaktdaten und darf nicht öffentlich zugänglich gemacht werden.
"""

    (target_dir / "README.md").write_text(readme_content, encoding="utf-8")
    print(f"Saved README.md to {target_dir / 'README.md'}")
    print("All exports successfully finished!")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/private/var/folders/9r/b80trnm93kv5yzf9vld4jmgw0000gn/T/opencode/Databases"
    export_all(target)
