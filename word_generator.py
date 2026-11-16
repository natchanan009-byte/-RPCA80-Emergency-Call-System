"""
Word Document Generator for Daily Incident Reports
ระบบสร้างเอกสาร Microsoft Word รายงานประจำวันรับแจ้งเป็นหลักฐาน
"""

import os
from datetime import datetime
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL

REPORTS_DIR = 'daily_reports'

def ensure_reports_directory():
    """สร้างโฟลเดอร์สำหรับเก็บรายงานถ้ายังไม่มี"""
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    return REPORTS_DIR

def format_thai_date(dt):
    """แปลงวันที่เป็นรูปแบบภาษาไทย"""
    thai_months = [
        'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
        'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
    ]
    thai_year = dt.year + 543
    return f"{dt.day} {thai_months[dt.month - 1]} {thai_year}"

def format_thai_time(dt):
    """แปลงเวลาเป็นรูปแบบไทย"""
    return dt.strftime('%H:%M น.')

def set_thai_font(run, size=16):
    """ตั้งค่าฟอนต์ภาษาไทย"""
    run.font.name = 'TH Sarabun New'
    run.font.size = Pt(size)
    # Set font for both ASCII and Complex Script
    run._element.rPr.rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii', 'TH Sarabun New')
    run._element.rPr.rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}cs', 'TH Sarabun New')

def generate_daily_incident_report(incident_data, citizen_data):
    """
    สร้างเอกสาร Word รายงานประจำวันรับแจ้งเป็นหลักฐาน

    Args:
        incident_data: ข้อมูลเหตุการณ์ (dict)
        citizen_data: ข้อมูลประชาชนผู้แจ้ง (dict)

    Returns:
        str: path ของไฟล์ที่สร้าง
    """

    # สร้างเอกสารใหม่
    doc = Document()

    # ตั้งค่า margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # === หัวเอกสาร ===

    # บรรทัดที่ 1: สำนักงานตำรวจแห่งชาติ
    header1 = doc.add_paragraph()
    header1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header1.add_run('สำนักงานตำรวจแห่งชาติ')
    set_thai_font(run, 18)
    run.bold = True

    # บรรทัดที่ 2: รายงานประจำวันรับแจ้งเป็นหลักฐาน
    header2 = doc.add_paragraph()
    header2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header2.add_run('รายงานประจำวันรับแจ้งเป็นหลักฐาน')
    set_thai_font(run, 18)
    run.bold = True

    # บรรทัดที่ 3: ชื่อหน่วยงาน (สามารถแก้ไขได้)
    header3 = doc.add_paragraph()
    header3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header3.add_run('(ระบบแจ้งความออนไลน์)')
    set_thai_font(run, 16)

    # เว้นบรรทัด
    doc.add_paragraph()

    # === ข้อมูลรายการ ===

    # Parse datetime - รองรับหลายรูปแบบ
    try:
        if isinstance(incident_data['created_at'], str):
            # ลองหลายรูปแบบ
            created_at_str = incident_data['created_at'].replace('Z', '+00:00')
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except:
                # ถ้า parse ไม่ได้ ลองรูปแบบ SQLite
                try:
                    created_at = datetime.strptime(incident_data['created_at'], '%Y-%m-%d %H:%M:%S')
                except:
                    # ถ้ายัง parse ไม่ได้ ใช้เวลาปัจจุบัน
                    created_at = datetime.now()
        else:
            created_at = incident_data['created_at']
    except:
        created_at = datetime.now()

    # เลขที่รายการ
    p = doc.add_paragraph()
    run = p.add_run(f"เลขที่รายการ: {incident_data['reference_code']}")
    set_thai_font(run, 16)
    run.bold = True

    # วันที่และเวลา
    p = doc.add_paragraph()
    run = p.add_run(f"วันที่: {format_thai_date(created_at)}  เวลา: {format_thai_time(created_at)}")
    set_thai_font(run, 16)

    # เว้นบรรทัด
    doc.add_paragraph()

    # === สร้างตาราง ===

    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # หัวตาราง
    header_cells = table.rows[0].cells
    header_cells[0].text = 'รายการ'
    header_cells[1].text = 'รายละเอียด'

    # ตั้งค่าฟอนต์หัวตาราง
    for cell in header_cells:
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                set_thai_font(run, 16)
                run.bold = True
        # สีพื้นหลัง
        from docx.oxml import parse_xml
        shading_elm = parse_xml(r'<w:shd {} w:fill="D3D3D3"/>'.format(
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'))
        cell._element.get_or_add_tcPr().append(shading_elm)

    # แถวข้อมูล
    data_rows = [
        ('ชื่อผู้แจ้ง', citizen_data.get('full_name', 'ไม่ระบุ')),
        ('เบอร์โทรศัพท์', citizen_data.get('phone_number', 'ไม่ระบุ')),
        ('ที่อยู่', citizen_data.get('address', 'ไม่ระบุ')),
        ('ชื่อบัญชีผู้ใช้', citizen_data.get('username', 'ไม่ระบุ')),
        ('ประเภทเหตุ', get_incident_type_thai(incident_data.get('incident_type', 'other'))),
        ('รายละเอียดเหตุการณ์', incident_data.get('details', 'ไม่ระบุรายละเอียด')),
        ('สถานที่เกิดเหตุ', f"พิกัด Latitude: {incident_data['latitude']}, Longitude: {incident_data['longitude']}"),
        ('แหล่งที่มาของตำแหน่ง', 'GPS อัตโนมัติ' if incident_data['location_source'] == 'gps' else 'ระบุด้วยตนเอง'),
    ]

    for label, value in data_rows:
        row_cells = table.add_row().cells
        row_cells[0].text = label
        row_cells[1].text = str(value)

        # ตั้งค่าฟอนต์
        for i, cell in enumerate(row_cells):
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for paragraph in cell.paragraphs:
                if i == 0:  # คอลัมน์แรก (ชื่อฟิลด์)
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in paragraph.runs:
                    set_thai_font(run, 16)
                    if i == 0:
                        run.bold = True

    # เว้นบรรทัด
    doc.add_paragraph()
    doc.add_paragraph()

    # === ส่วนลงนาม ===

    # ผู้แจ้ง
    p = doc.add_paragraph()
    run = p.add_run('ลงชื่อ ................................. ผู้แจ้ง')
    set_thai_font(run, 16)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p = doc.add_paragraph()
    run = p.add_run(f'       ({citizen_data.get("full_name", ".................................")})')
    set_thai_font(run, 16)

    # เว้นบรรทัด
    doc.add_paragraph()

    # เจ้าหน้าที่ผู้รับแจ้ง
    p = doc.add_paragraph()
    run = p.add_run('ลงชื่อ ................................. เจ้าหน้าที่ผู้รับแจ้ง')
    set_thai_font(run, 16)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p = doc.add_paragraph()
    run = p.add_run('       (..................................)')
    set_thai_font(run, 16)

    # เว้นบรรทัด
    doc.add_paragraph()

    # ผู้บันทึก
    p = doc.add_paragraph()
    run = p.add_run('ลงชื่อ ................................. ผู้บันทึก')
    set_thai_font(run, 16)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p = doc.add_paragraph()
    run = p.add_run('       (..................................)')
    set_thai_font(run, 16)

    # เว้นบรรทัด
    doc.add_paragraph()
    doc.add_paragraph()

    # === หมายเหตุ ===
    p = doc.add_paragraph()
    run = p.add_run('หมายเหตุ: ')
    set_thai_font(run, 14)
    run.bold = True
    run = p.add_run('เอกสารนี้เป็นเอกสารร่างที่ระบบสร้างขึ้นโดยอัตโนมัติ โปรดให้เจ้าหน้าที่ตรวจสอบความถูกต้องของข้อมูลก่อนรับรองเป็นเอกสารทางราชการ')
    set_thai_font(run, 14)
    run.italic = True
    run.font.color.rgb = RGBColor(128, 128, 128)

    # === บันทึกไฟล์ ===

    ensure_reports_directory()

    # สร้างชื่อไฟล์
    date_str = created_at.strftime('%Y%m%d_%H%M%S')
    filename = f"daily_report_{incident_data['id']}_{date_str}.docx"
    filepath = os.path.join(REPORTS_DIR, filename)

    # บันทึก
    doc.save(filepath)

    return filepath

def get_incident_type_thai(incident_type):
    """แปลงประเภทเหตุเป็นภาษาไทย"""
    types = {
        'accident': 'อุบัติเหตุ',
        'medical': 'บุคคลต้องการความช่วยเหลือทางการแพทย์',
        'dispute': 'ทะเลาะวิวาท',
        'suspicious': 'บุคคลหรือทรัพย์สินน่าสงสัย',
        'theft': 'ลักทรัพย์',
        'other': 'อื่น ๆ'
    }
    return types.get(incident_type, 'อื่น ๆ')

def get_report_path(incident_id):
    """ค้นหาไฟล์รายงานของเหตุการณ์"""
    ensure_reports_directory()

    for filename in os.listdir(REPORTS_DIR):
        if filename.startswith(f"daily_report_{incident_id}_") and filename.endswith('.docx'):
            return os.path.join(REPORTS_DIR, filename)

    return None
