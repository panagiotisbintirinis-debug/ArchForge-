import sys
sys.path.insert(0, '/home/user/ArchForge-')
from archforge.ui.pbr_viewport import pbr_page_html
from archforge.rendering.sun import sun_position
open(sys.argv[1], 'w').write(pbr_page_html())
print(sun_position(11.0, 7))
