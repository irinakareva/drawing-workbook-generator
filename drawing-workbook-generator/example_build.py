from pathlib import Path
from workbook_generator_backend import WorkbookBuilder

ROOT=Path('/mnt/data')
BUILD=ROOT/'workbook_v5_build'
ASSETS=BUILD/'assets'
ASSETS.mkdir(parents=True, exist_ok=True)

SRC={
    'scissors': ROOT/'workbook_v2_build/assets/scissors_clear.png',
    'chair': ROOT/'workbook_v2_build/assets/chair_clear.png',
    'mug': ROOT/'workbook_v2_build/assets/mug_clear.png',
    'earbuds': ROOT/'workbook_v2_build/assets/earbuds_clear.png',
    'ginkgo': ROOT/'workbook_v2_build/assets/ginkgo_clear.png',
    'lily': ROOT/'workbook_v2_build/assets/calla_clear.png',
    'classflower': ROOT/'workbook_v2_build/assets/classflower_clear.png',
}

DEFAULT_EXERCISES = dict(
    blind_contour=True,
    regular_contour=True,
    sam=True,
    upside_down=True,
    negative_space=True,
    three_value=False,
    five_value=False,
    progressive_focus=False,
    integrated=False,
)

def spec(key, subject, description, values=False, focus=False, integrated=False):
    ex = DEFAULT_EXERCISES.copy()
    ex['three_value'] = values
    ex['five_value'] = values
    ex['progressive_focus'] = focus
    ex['integrated'] = integrated
    return {
        'key': key,
        'subject': subject,
        'description': description,
        'image_path': SRC[key],
        'exercises': ex,
        'include_compact': True,
        'include_large': True,
        'levels': ['fine','medium','coarse','cross'],
    }

specs = [
    spec('scissors','SCISSORS','Simple hard-edged object: angles, openings, and clear negative space.',False,False,False),
    spec('chair','CHAIR','Simple structure with more relationships and larger negative spaces.',False,False,False),
    spec('mug','MUG','Simple curved object; add value grouping and progressive focus.',True,True,True),
    spec('earbuds','EARBUDS','More complex line flow and enclosed spaces; values are intentionally skipped.',False,False,False),
    spec('ginkgo','GINKGO','Organic contours, overlaps, negative space, and values.',True,True,True),
    spec('lily','CALLA LILY','More complex organic form and value structure.',True,True,True),
    spec('classflower','CLASS FLOWER','Most complex current reference; full process for class planning.',True,True,True),
]

if __name__ == '__main__':
    out_docx = ROOT/'Drawing_Practice_Workbook_05_Tight.docx'
    out_pdf = ROOT/'Drawing_Practice_Workbook_05_Tight.pdf'
    builder = WorkbookBuilder(ASSETS)
    builder.build('Drawing Practice Workbook 05', specs, out_docx, out_pdf)
    print(out_docx)
    print(out_pdf)
