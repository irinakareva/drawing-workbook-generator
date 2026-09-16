import streamlit as st
from pathlib import Path
from datetime import datetime
import re
from workbook_generator_backend import WorkbookBuilder

ROOT = Path('/mnt/data')
APP_ROOT = ROOT / 'workbook_app_runs'
APP_ROOT.mkdir(parents=True, exist_ok=True)

def slugify(text):
    text = re.sub(r'[^A-Za-z0-9]+', '_', text).strip('_')
    return text or 'image'

st.set_page_config(page_title='Drawing Workbook Generator', layout='wide')
st.title('Drawing Workbook Generator')
st.write('Upload one or more reference images, choose which exercises to include for each image, and generate a workbook as DOCX and PDF.')

workbook_title = st.text_input('Workbook title', value='Custom Drawing Practice Workbook')
include_compact = st.checkbox('Include compact pages', value=True)
include_large = st.checkbox('Include large-study pages', value=True)

uploaded_files = st.file_uploader('Upload one or more images', type=['png','jpg','jpeg','webp'], accept_multiple_files=True)

specs = []
if uploaded_files:
    st.subheader('Per-image settings')
    for idx, up in enumerate(uploaded_files, start=1):
        with st.expander(f'Image {idx}: {up.name}', expanded=True):
            subject = st.text_input(f'Display name for {up.name}', value=Path(up.name).stem, key=f'subject_{idx}')
            description = st.text_input(f'Short description for {up.name}', value='', key=f'desc_{idx}')
            c1, c2, c3 = st.columns(3)
            with c1:
                blind = st.checkbox('Blind contour', value=True, key=f'blind_{idx}')
                regular = st.checkbox('Regular contour', value=True, key=f'regular_{idx}')
                sam = st.checkbox('SAM / mapping', value=True, key=f'sam_{idx}')
            with c2:
                upside = st.checkbox('Upside-down drawing', value=True, key=f'upside_{idx}')
                neg = st.checkbox('Negative space', value=True, key=f'neg_{idx}')
                three = st.checkbox('3-value study', value=False, key=f'three_{idx}')
            with c3:
                five = st.checkbox('5-value study', value=False, key=f'five_{idx}')
                prog = st.checkbox('Progressive focus', value=False, key=f'prog_{idx}')
                integ = st.checkbox('Integrated study', value=False, key=f'integ_{idx}')

            levels = st.multiselect(
                f'Scaffold levels for {up.name}',
                options=['fine','medium','coarse','cross'],
                default=['fine','medium','coarse','cross'],
                key=f'levels_{idx}'
            )

            specs.append({
                'uploaded_file': up,
                'subject': subject,
                'description': description,
                'exercises': {
                    'blind_contour': blind,
                    'regular_contour': regular,
                    'sam': sam,
                    'upside_down': upside,
                    'negative_space': neg,
                    'three_value': three,
                    'five_value': five,
                    'progressive_focus': prog,
                    'integrated': integ,
                },
                'levels': levels or ['fine','medium','coarse','cross'],
            })

if uploaded_files and st.button('Generate workbook', type='primary'):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = APP_ROOT / timestamp
    upload_dir = run_dir / 'uploads'
    asset_dir = run_dir / 'assets'
    upload_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    build_specs = []
    for i, spec in enumerate(specs, start=1):
        name_slug = slugify(spec['subject'])
        ext = Path(spec['uploaded_file'].name).suffix or '.png'
        image_path = upload_dir / f'{i:02d}_{name_slug}{ext}'
        image_path.write_bytes(spec['uploaded_file'].getbuffer())
        build_specs.append({
            'key': f'{i:02d}_{name_slug}',
            'subject': spec['subject'],
            'description': spec['description'],
            'image_path': image_path,
            'exercises': spec['exercises'],
            'include_compact': include_compact,
            'include_large': include_large,
            'levels': spec['levels'],
        })

    builder = WorkbookBuilder(asset_dir)
    docx_path = run_dir / f'{slugify(workbook_title)}.docx'
    pdf_path = run_dir / f'{slugify(workbook_title)}.pdf'
    with st.spinner('Generating workbook...'):
        builder.build(workbook_title, build_specs, docx_path, pdf_path)

    st.success('Workbook generated.')
    st.write(f'DOCX: {docx_path}')
    st.write(f'PDF: {pdf_path}')
    st.download_button('Download DOCX', data=docx_path.read_bytes(), file_name=docx_path.name)
    st.download_button('Download PDF', data=pdf_path.read_bytes(), file_name=pdf_path.name)
    st.write('Run folder:')
    st.code(str(run_dir))
