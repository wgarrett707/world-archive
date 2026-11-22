"""Block colours, shapes, and lookup tables shared by the Java and Bedrock loaders.

Every block is resolved to a (name, variant) pair using legacy/Bedrock style names
(e.g. ("wool", "red"), ("planks", "spruce")), then to a palette entry describing how to draw it.
"""
import hashlib
import numpy as np

DYES = ['white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime', 'pink', 'gray',
        'silver', 'cyan', 'purple', 'blue', 'brown', 'green', 'red', 'black']

DYE_RGB = {
    'white': (233, 236, 236), 'orange': (240, 118, 19), 'magenta': (189, 68, 179),
    'light_blue': (58, 175, 217), 'yellow': (248, 197, 39), 'lime': (112, 185, 25),
    'pink': (237, 141, 172), 'gray': (62, 68, 71), 'silver': (142, 142, 134),
    'cyan': (21, 137, 145), 'purple': (121, 42, 172), 'blue': (53, 57, 157),
    'brown': (114, 71, 40), 'green': (84, 109, 27), 'red': (160, 39, 34), 'black': (20, 21, 25),
}
TERRACOTTA_RGB = {
    'white': (209, 178, 161), 'orange': (161, 83, 37), 'magenta': (149, 88, 108),
    'light_blue': (113, 108, 137), 'yellow': (186, 133, 35), 'lime': (103, 117, 52),
    'pink': (161, 78, 78), 'gray': (57, 42, 35), 'silver': (135, 106, 97),
    'cyan': (86, 91, 91), 'purple': (118, 70, 86), 'blue': (74, 59, 91),
    'brown': (77, 51, 35), 'green': (76, 83, 42), 'red': (143, 61, 46), 'black': (37, 22, 16),
}
WOODS = ['oak', 'spruce', 'birch', 'jungle', 'acacia', 'dark_oak']
PLANK_RGB = {
    'oak': (162, 130, 78), 'spruce': (114, 84, 48), 'birch': (192, 175, 121),
    'jungle': (160, 115, 80), 'acacia': (168, 90, 50), 'dark_oak': (66, 43, 20),
    'crimson': (101, 48, 70), 'warped': (43, 104, 99), 'mangrove': (117, 54, 48),
    'cherry': (226, 178, 172), 'bamboo': (193, 173, 80),
}
LOG_RGB = {
    'oak': (109, 85, 50), 'spruce': (58, 37, 16), 'birch': (216, 215, 210),
    'jungle': (85, 67, 25), 'acacia': (103, 96, 86), 'dark_oak': (60, 46, 26),
    'crimson': (92, 25, 29), 'warped': (58, 58, 77),
}
LEAF_RGB = {
    'oak': (59, 122, 30), 'spruce': (56, 92, 56), 'birch': (98, 132, 58),
    'jungle': (48, 128, 22), 'acacia': (70, 115, 28), 'dark_oak': (46, 104, 22),
}
STONE_RGB = {
    'stone': (125, 125, 125), 'granite': (149, 103, 85), 'smooth_granite': (154, 106, 89),
    'granite_smooth': (154, 106, 89), 'diorite': (188, 188, 188), 'smooth_diorite': (193, 193, 195),
    'diorite_smooth': (193, 193, 195), 'andesite': (136, 136, 136), 'smooth_andesite': (132, 134, 133),
    'andesite_smooth': (132, 134, 133),
}

# Material keywords used for stairs/slabs/walls/fences and anything else not in the table.
MATERIAL_RGB = [
    ('red_nether_brick', (69, 7, 9)), ('nether_brick', (44, 21, 26)),
    ('red_sandstone', (186, 99, 29)), ('smooth_sandstone', (223, 214, 170)), ('sandstone', (216, 203, 155)),
    ('mossy_stone_brick', (115, 121, 105)), ('stone_brick', (122, 121, 122)), ('stonebrick', (122, 121, 122)),
    ('mossy_cobblestone', (110, 118, 94)), ('cobblestone', (122, 122, 122)), ('cobble', (122, 122, 122)),
    ('polished_blackstone', (53, 48, 56)), ('blackstone', (42, 36, 41)), ('deepslate', (80, 80, 82)),
    ('dark_prismarine', (51, 91, 75)), ('prismarine_brick', (99, 171, 158)), ('prismarine', (99, 156, 151)),
    ('end_brick', (218, 224, 162)), ('end_stone', (219, 222, 158)), ('purpur', (169, 125, 169)),
    ('quartz', (235, 229, 222)), ('brick', (150, 97, 83)), ('mud_brick', (137, 103, 79)),
    ('granite', (154, 106, 89)), ('diorite', (190, 190, 192)), ('andesite', (134, 135, 134)),
    ('smooth_stone', (158, 158, 158)), ('stone', (125, 125, 125)), ('copper', (192, 107, 79)),
    ('crimson', (101, 48, 70)), ('warped', (43, 104, 99)), ('dark_oak', (66, 43, 20)),
    ('spruce', (114, 84, 48)), ('birch', (192, 175, 121)), ('jungle', (160, 115, 80)),
    ('acacia', (168, 90, 50)), ('mangrove', (117, 54, 48)), ('cherry', (226, 178, 172)),
    ('bamboo', (193, 173, 80)), ('oak', (162, 130, 78)), ('wood', (162, 130, 78)),
    ('iron', (200, 200, 200)), ('gold', (246, 208, 61)), ('diamond', (98, 237, 228)),
    ('emerald', (42, 203, 87)), ('netherite', (66, 61, 63)), ('obsidian', (15, 10, 24)),
    ('ice', (145, 183, 253)), ('snow', (249, 254, 254)), ('sand', (219, 207, 163)),
    ('dirt', (134, 96, 67)), ('mud', (60, 57, 60)), ('glass', (200, 220, 230)),
    ('wool', (233, 236, 236)), ('clay', (160, 166, 179)), ('terracotta', (152, 94, 67)),
]

# name -> (rgb, kind, shape, extra)
#   kind:  solid | trans | overlay | skip
#   shape: full | slab_b | slab_t | post | small
#   extra: dict with optional 'side' rgb, 'alpha', 'blend', 'glow'
T = {}


def _b(names, rgb, kind='solid', shape='full', **extra):
    for n in names.split():
        T[n] = (rgb, kind, shape, extra)


# --- Natural terrain
_b('stone', (125, 125, 125))
_b('grass', (104, 158, 58), side=(134, 96, 67))
_b('grass_block', (104, 158, 58), side=(134, 96, 67))
_b('dirt', (134, 96, 67))
_b('podzol', (91, 63, 24), side=(134, 96, 67))
_b('mycelium', (111, 99, 105), side=(134, 96, 67))
_b('farmland', (81, 44, 15), side=(134, 96, 67))
_b('grass_path dirt_path', (148, 122, 65), side=(134, 96, 67))
_b('bedrock', (85, 85, 85))
_b('sand', (219, 207, 163))
_b('red_sand', (190, 102, 33))
_b('gravel', (131, 127, 126))
_b('clay', (160, 166, 179))
_b('sandstone', (216, 203, 155))
_b('red_sandstone', (186, 99, 29))
_b('hardened_clay terracotta', (152, 94, 67))
_b('snow snow_block', (249, 254, 254))
_b('packed_ice', (141, 180, 250))
_b('blue_ice', (116, 167, 253))
_b('obsidian', (15, 10, 24))
_b('crying_obsidian', (40, 10, 70))
_b('netherrack', (97, 38, 38))
_b('soul_sand', (81, 62, 50))
_b('soul_soil', (75, 57, 46))
_b('glowstone', (220, 180, 110), glow=True)
_b('magma', (142, 63, 31), glow=True)
_b('end_stone', (219, 222, 158))
_b('cactus', (85, 127, 43))
_b('pumpkin carved_pumpkin', (198, 118, 24))
_b('lit_pumpkin', (227, 150, 40), glow=True)
_b('melon_block melon', (111, 145, 30))
_b('brown_mushroom_block', (149, 111, 81))
_b('red_mushroom_block', (200, 46, 45))
_b('mushroom_stem', (203, 196, 185))
_b('crimson_nylium', (130, 31, 31), side=(97, 38, 38))
_b('warped_nylium', (43, 114, 101), side=(97, 38, 38))
_b('basalt polished_basalt', (80, 81, 86))
_b('nether_wart_block', (114, 2, 2))
_b('warped_wart_block', (22, 119, 121))
_b('shroomlight', (240, 146, 70), glow=True)
_b('bone_block', (209, 206, 179))
_b('sponge', (195, 192, 74))
_b('coal_ore', (115, 115, 115))
_b('iron_ore', (136, 130, 127))
_b('gold_ore nether_gold_ore', (143, 140, 125))
_b('diamond_ore', (121, 141, 140))
_b('redstone_ore lit_redstone_ore', (133, 107, 107))
_b('lapis_ore', (99, 110, 132))
_b('emerald_ore', (117, 136, 124))
_b('quartz_ore', (117, 65, 62))
_b('ancient_debris', (96, 64, 56))
_b('monster_egg', (125, 125, 125))
_b('coral_block', (60, 100, 220))

# --- Fluids / translucent
_b('water flowing_water', (62, 118, 222), 'trans', alpha=0.78)
_b('lava flowing_lava', (212, 96, 14), glow=True)
_b('ice frosted_ice', (145, 183, 253), 'trans', alpha=0.72)
_b('glass', (210, 228, 236), 'trans', alpha=0.32)
_b('glass_pane', (210, 228, 236), 'trans', alpha=0.28)
_b('stained_glass', (255, 255, 255), 'trans', alpha=0.5)
_b('stained_glass_pane', (255, 255, 255), 'trans', alpha=0.45)
_b('slime', (111, 192, 91), 'trans', alpha=0.8)
_b('honey_block', (251, 185, 52), 'trans', alpha=0.8)
_b('portal', (110, 30, 210), 'trans', alpha=0.6, glow=True)
_b('end_portal end_gateway', (12, 20, 30))

# --- Wood & building blocks
_b('planks', (162, 130, 78))
_b('log log2 wood', (109, 85, 50))
_b('leaves leaves2', (59, 122, 30))
_b('bookshelf', (117, 94, 59), side=(117, 76, 50))
_b('crafting_table', (130, 100, 60))
_b('cobblestone', (122, 122, 122))
_b('mossy_cobblestone', (110, 118, 94))
_b('stonebrick', (122, 121, 122))
_b('brick_block', (150, 97, 83))
_b('nether_brick', (44, 21, 26))
_b('red_nether_brick', (69, 7, 9))
_b('quartz_block', (235, 229, 222))
_b('purpur_block purpur_pillar', (169, 125, 169))
_b('end_bricks', (218, 224, 162))
_b('prismarine', (99, 156, 151))
_b('sea_lantern seaLantern', (180, 205, 196), glow=True)
_b('wool', (233, 236, 236))
_b('concrete', (233, 236, 236))
_b('concrete_powder', (233, 236, 236))
_b('stained_hardened_clay', (209, 178, 161))
_b('smooth_stone', (158, 158, 158))
_b('blackstone', (42, 36, 41))
_b('polished_blackstone polished_blackstone_bricks', (53, 48, 56))
_b('gold_block', (246, 208, 61))
_b('iron_block', (220, 220, 220))
_b('diamond_block', (98, 237, 228))
_b('emerald_block', (42, 203, 87))
_b('lapis_block', (30, 67, 140))
_b('redstone_block', (175, 24, 5))
_b('coal_block', (16, 15, 15))
_b('netherite_block', (66, 61, 63))
_b('quartz_bricks', (234, 229, 221))
_b('hay_block', (166, 139, 12))
_b('dried_kelp_block', (50, 59, 38))
_b('tnt', (219, 68, 52), side=(180, 60, 40))
_b('noteblock jukebox', (88, 58, 40))
_b('furnace lit_furnace smoker lit_smoker blast_furnace lit_blast_furnace', (110, 110, 110))
_b('dispenser dropper observer', (110, 110, 110))
_b('piston sticky_piston pistonArmCollision piston_head', (150, 130, 100))
_b('command_block repeating_command_block chain_command_block', (180, 135, 110))
_b('mob_spawner', (35, 50, 65))
_b('beacon', (117, 220, 215), glow=True)
_b('redstone_lamp', (95, 54, 30))
_b('lit_redstone_lamp', (230, 170, 100), glow=True)
_b('chest trapped_chest barrel', (162, 116, 48))
_b('ender_chest', (40, 55, 55))
_b('enchanting_table', (60, 30, 40))
_b('anvil', (68, 68, 68))
_b('cauldron', (55, 55, 55))
_b('hopper', (60, 60, 60))
_b('bed', (142, 22, 22), shape='slab_b')
_b('cake', (230, 220, 210), shape='slab_b')
_b('daylight_detector daylight_detector_inverted', (130, 116, 94), shape='slab_b')
_b('end_portal_frame', (90, 120, 100), shape='slab_b')
_b('beehive bee_nest', (180, 145, 80))
_b('loom cartography_table fletching_table smithing_table lectern composter', (130, 100, 60))
_b('stonecutter_block stonecutter grindstone', (120, 120, 120))
_b('target', (229, 175, 168))
_b('structure_block jigsaw', (90, 75, 90))
_b('shulker_box undyed_shulker_box', (150, 105, 150))
_b('chorus_plant', (93, 57, 93), shape='post')
_b('chorus_flower', (151, 120, 151))
_b('dragon_egg', (12, 9, 15), shape='small')

# --- Thin/partial blocks
_b('fence nether_brick_fence spruce_fence birch_fence jungle_fence dark_oak_fence acacia_fence', (162, 130, 78), shape='post')
_b('cobblestone_wall', (122, 122, 122), shape='post')
_b('iron_bars', (136, 139, 135), shape='post')
_b('wooden_door spruce_door birch_door jungle_door acacia_door dark_oak_door', (150, 115, 65), shape='post')
_b('iron_door', (190, 190, 190), shape='post')
_b('reeds', (110, 170, 75), shape='post')
_b('bamboo', (95, 140, 40), shape='post')
_b('end_rod', (240, 230, 220), shape='post', glow=True)
_b('torch', (255, 210, 90), shape='small', glow=True)
_b('redstone_torch unlit_redstone_torch', (200, 30, 10), shape='small')
_b('lantern soul_lantern', (90, 80, 70), shape='small', glow=True)
_b('flower_pot', (122, 67, 50), shape='small')
_b('skull', (200, 200, 200), shape='small')
_b('brewing_stand', (120, 105, 90), shape='small')
_b('bell', (250, 210, 60), shape='small')
_b('campfire soul_campfire', (200, 110, 40), shape='small', glow=True)
_b('sapling', (70, 130, 40), shape='small')
_b('brown_mushroom', (150, 110, 80), shape='small')
_b('red_mushroom', (200, 40, 40), shape='small')
_b('scaffolding', (190, 160, 90), shape='post')

# --- Flat things painted onto the block below
_b('snow_layer', (249, 254, 254), 'overlay', blend=1.0)
_b('carpet', (233, 236, 236), 'overlay', blend=1.0)
_b('waterlily', (32, 128, 48), 'overlay', blend=0.9)
_b('rail golden_rail detector_rail activator_rail', (125, 110, 85), 'overlay', blend=0.6)
_b('redstone_wire', (190, 20, 10), 'overlay', blend=0.55)
_b('stone_pressure_plate wooden_pressure_plate light_weighted_pressure_plate heavy_weighted_pressure_plate', (150, 140, 120), 'overlay', blend=0.4)
_b('unpowered_repeater powered_repeater unpowered_comparator powered_comparator', (160, 150, 150), 'overlay', blend=0.7)
_b('trapdoor iron_trapdoor', (130, 100, 60), 'overlay', blend=0.5)
_b('wheat', (190, 175, 60), 'overlay', blend=0.75)
_b('carrots potatoes beetroot beetroots', (80, 150, 40), 'overlay', blend=0.75)
_b('nether_wart', (140, 20, 20), 'overlay', blend=0.7)
_b('yellow_flower', (240, 220, 40), 'overlay', blend=0.35)
_b('red_flower', (210, 40, 40), 'overlay', blend=0.35)
_b('pumpkin_stem melon_stem', (120, 150, 60), 'overlay', blend=0.3)

# --- Invisible / ignored
_b('air cave_air void_air structure_void barrier light_block tallgrass deadbush fire soul_fire web '
   'tripwire tripwireHook tripwire_hook lever stone_button wooden_button ladder vine standing_sign '
   'wall_sign wall_banner standing_banner seagrass kelp tall_grass double_plant cocoa unknown '
   'invisibleBedrock moving_block movingBlock info_update info_update2 reserved6 frame item_frame '
   'twisting_vines weeping_vines coral coral_fan coral_fan_dead coral_fan_hang coral_fan_hang2 '
   'coral_fan_hang3 sweet_berry_bush crimson_roots warped_roots nether_sprouts sea_pickle '
   'spruce_standing_sign birch_standing_sign jungle_standing_sign acacia_standing_sign darkoak_standing_sign '
   'spruce_wall_sign birch_wall_sign jungle_wall_sign acacia_wall_sign darkoak_wall_sign '
   'crimson_standing_sign warped_standing_sign crimson_wall_sign warped_wall_sign bubble_column', (0, 0, 0), 'skip')

# How strongly each block suggests a player built here (for picking interesting areas).
# Blocks that also generate naturally in villages, strongholds, mineshafts, etc. get a low weight
# so that a plain village doesn't outrank a real build.
_STRONG = '''wool concrete concrete_powder stained_glass stained_glass_pane quartz_block quartz_bricks
gold_block iron_block diamond_block emerald_block lapis_block redstone_block coal_block netherite_block
beacon redstone_lamp lit_redstone_lamp tnt enchanting_table anvil hopper dispenser dropper piston
sticky_piston redstone_wire unpowered_repeater powered_repeater unpowered_comparator powered_comparator
command_block repeating_command_block chain_command_block jukebox noteblock observer slime honey_block
ender_chest shulker_box glowstone end_rod daylight_detector daylight_detector_inverted target
polished_blackstone_bricks lit_pumpkin iron_door iron_trapdoor'''.split()
_MEDIUM = '''glass brick_block stained_hardened_clay purpur_block purpur_pillar end_bricks
carpet wall_banner standing_banner brewing_stand cake bed red_nether_brick'''.split()
_WEAK = '''glass_pane torch crafting_table furnace lit_furnace chest trapped_chest wooden_door
fence_gate cobblestone_wall hay_block barrel smoker blast_furnace lectern bell scaffolding lantern
composter loom cartography_table fletching_table smithing_table grindstone stonecutter_block
cauldron flower_pot smooth_stone double_wooden_slab ladder bookshelf'''.split()
# Generated in huge numbers by strongholds, mineshafts, igloos etc. — nearly worthless as a signal.
_NATURALISH = '''planks fence stonebrick iron_bars rail golden_rail powered_rail detector_rail activator_rail
mossy_cobblestone mob_spawner'''.split()
BUILT_W = {n: 1.0 for n in _STRONG}
BUILT_W.update({n: 0.5 for n in _MEDIUM})
BUILT_W.update({n: 0.12 for n in _WEAK})
BUILT_W.update({n: 0.01 for n in _NATURALISH})
BUILT_W.update({'planks': 0.04, 'fence': 0.04})  # mineshafts are full of these
# Signs, item frames and armour stands are nearly always player-made and mark points of interest.
BUILT_W.update({n: 25.0 for n in 'wall_sign standing_sign item_frame frame'.split()})


def built_weight(name):
    base = name.replace('minecraft:', '')
    if base in BUILT_W:
        return BUILT_W[base]
    if 'sign' in base:
        return 25.0
    if 'glazed_terracotta' in base or base.endswith('_concrete') or base.endswith('_wool')             or base.endswith('shulker_box') or base.endswith('stained_glass'):
        return 1.0
    if 'stone_brick' in base:
        return 0.01
    if base.endswith('_stairs') or base.endswith('_slab') or base.endswith('_door')             or base.endswith('_fence') or base.endswith('_fence_gate') or base.endswith('_planks')             or base.endswith('_trapdoor'):
        return 0.12
    return 0.0


GLOW = set()


def _hash_rgb(s):
    h = hashlib.md5(s.encode()).digest()
    return (110 + h[0] % 80, 100 + h[1] % 80, 95 + h[2] % 80)


def _material(name):
    for kw, rgb in MATERIAL_RGB:
        if kw in name:
            return rgb
    return None


def describe(name, variant):
    """Return (rgb, kind, shape, extra) for a block."""
    name = name.replace('minecraft:', '')
    v = variant or ''
    if name in T:
        rgb, kind, shape, extra = T[name]
        extra = dict(extra)
        if kind == 'skip':
            return T[name]
        # Variant colouring
        if name in ('wool', 'concrete', 'carpet', 'shulker_box'):
            rgb = DYE_RGB.get(v, rgb)
        elif name == 'concrete_powder':
            c = DYE_RGB.get(v, rgb); rgb = tuple(min(255, int(x * 0.85 + 40)) for x in c)
        elif name in ('stained_hardened_clay',):
            rgb = TERRACOTTA_RGB.get(v, rgb)
        elif name in ('stained_glass', 'stained_glass_pane'):
            rgb = DYE_RGB.get(v, (200, 200, 200))
        elif name == 'planks':
            rgb = PLANK_RGB.get(v, rgb)
        elif name in ('log', 'log2', 'wood'):
            rgb = LOG_RGB.get(v, rgb)
        elif name in ('leaves', 'leaves2'):
            rgb = LEAF_RGB.get(v, rgb)
        elif name == 'stone':
            rgb = STONE_RGB.get(v, rgb)
        elif name == 'sand' and v == 'red':
            rgb = (190, 102, 33)
        elif name == 'dirt' and v in ('coarse',):
            rgb = (119, 85, 59)
        elif name == 'dirt' and v == 'podzol':
            rgb = (91, 63, 24); extra['side'] = (134, 96, 67)
        elif name == 'stonebrick' and 'mossy' in v:
            rgb = (115, 121, 105)
        elif name == 'prismarine':
            rgb = {'bricks': (99, 171, 158), 'dark': (51, 91, 75)}.get(v, rgb)
        elif name == 'red_flower':
            rgb = {'blue_orchid': (40, 160, 220), 'allium': (180, 110, 220), 'houstonia': (220, 225, 225),
                   'tulip_orange': (240, 130, 30), 'tulip_white': (230, 230, 230), 'tulip_pink': (240, 170, 200),
                   'oxeye': (230, 230, 200), 'cornflower': (70, 100, 220), 'lily_of_the_valley': (240, 240, 240)
                   }.get(v, rgb)
        elif name in ('fence',):
            rgb = PLANK_RGB.get(v, rgb)
        elif name == 'cobblestone_wall' and v:
            rgb = _material(v) or rgb
        return rgb, kind, shape, extra

    # Family names
    if 'glazed_terracotta' in name:
        col = name.replace('_glazed_terracotta', '')
        return DYE_RGB.get(col, (150, 150, 150)), 'solid', 'full', {}
    if name.endswith('shulker_box'):
        col = name.replace('_shulker_box', '')
        return DYE_RGB.get(col, (150, 105, 150)), 'solid', 'full', {}
    if name.endswith('_stairs'):
        return _material(name) or (125, 125, 125), 'solid', 'full', {}
    if 'slab' in name:
        mat = _material(v + ' ' + name) or (158, 158, 158)
        if 'double' in name:
            return mat, 'solid', 'full', {}
        return mat, 'solid', 'slab_t' if v.endswith('#top') else 'slab_b', {}
    if name.endswith('_wall') or name.endswith('fence') or name.endswith('fence_gate'):
        return _material(name) or (162, 130, 78), 'solid', 'post', {}
    if name.endswith('_door'):
        return _material(name) or (150, 115, 65), 'solid', 'post', {}
    if name.endswith('trapdoor'):
        return _material(name) or (130, 100, 60), 'overlay', 'full', {'blend': 0.5}
    if name.endswith('pressure_plate') or name.endswith('_button') or 'sign' in name or 'banner' in name:
        return (0, 0, 0), 'skip', 'full', {}
    if name.endswith('_carpet'):
        return DYE_RGB.get(name[:-7], (200, 200, 200)), 'overlay', 'full', {'blend': 1.0}
    if 'stripped' in name or name.endswith('_log') or name.endswith('_stem') or name.endswith('_hyphae'):
        return _material(name) or (109, 85, 50), 'solid', 'full', {}
    if name.endswith('leaves'):
        return (59, 122, 30), 'solid', 'full', {}
    if name.endswith('_planks'):
        return PLANK_RGB.get(name[:-7], (162, 130, 78)), 'solid', 'full', {}
    if 'coral' in name or 'vines' in name or 'roots' in name or 'sapling' in name or 'flower' in name:
        return (0, 0, 0), 'skip', 'full', {}
    m = _material(name)
    if m:
        return m, 'solid', 'full', {}
    return _hash_rgb(name), 'solid', 'full', {}


# --------------------------------------------------------------------------------------------
# Java 1.12 numeric IDs

JAVA_IDS = '''air stone grass dirt cobblestone planks sapling bedrock flowing_water water flowing_lava lava
sand gravel gold_ore iron_ore coal_ore log leaves sponge glass lapis_ore lapis_block dispenser sandstone
noteblock bed golden_rail detector_rail sticky_piston web tallgrass deadbush piston piston_head wool
piston_extension yellow_flower red_flower brown_mushroom red_mushroom gold_block iron_block
double_stone_slab stone_slab brick_block tnt bookshelf mossy_cobblestone obsidian torch fire mob_spawner
oak_stairs chest redstone_wire diamond_ore diamond_block crafting_table wheat farmland furnace lit_furnace
standing_sign wooden_door ladder rail stone_stairs wall_sign lever stone_pressure_plate iron_door
wooden_pressure_plate redstone_ore lit_redstone_ore unlit_redstone_torch redstone_torch stone_button
snow_layer ice snow cactus clay reeds jukebox fence pumpkin netherrack soul_sand glowstone portal
lit_pumpkin cake unpowered_repeater powered_repeater stained_glass trapdoor monster_egg stonebrick
brown_mushroom_block red_mushroom_block iron_bars glass_pane melon_block pumpkin_stem melon_stem vine
fence_gate brick_stairs stone_brick_stairs mycelium waterlily nether_brick nether_brick_fence
nether_brick_stairs nether_wart enchanting_table brewing_stand cauldron end_portal end_portal_frame
end_stone dragon_egg redstone_lamp lit_redstone_lamp double_wooden_slab wooden_slab cocoa
sandstone_stairs emerald_ore ender_chest tripwire_hook tripwire emerald_block spruce_stairs birch_stairs
jungle_stairs command_block beacon cobblestone_wall flower_pot carrots potatoes wooden_button skull anvil
trapped_chest light_weighted_pressure_plate heavy_weighted_pressure_plate unpowered_comparator
powered_comparator daylight_detector redstone_block quartz_ore hopper quartz_block quartz_stairs
activator_rail dropper stained_hardened_clay stained_glass_pane leaves2 log2 acacia_stairs
dark_oak_stairs slime barrier iron_trapdoor prismarine sea_lantern hay_block carpet hardened_clay
coal_block packed_ice double_plant standing_banner wall_banner daylight_detector_inverted red_sandstone
red_sandstone_stairs double_stone_slab2 stone_slab2 spruce_fence_gate birch_fence_gate jungle_fence_gate
dark_oak_fence_gate acacia_fence_gate spruce_fence birch_fence jungle_fence dark_oak_fence acacia_fence
spruce_door birch_door jungle_door acacia_door dark_oak_door end_rod chorus_plant chorus_flower
purpur_block purpur_pillar purpur_stairs purpur_double_slab purpur_slab end_bricks beetroots grass_path
end_gateway repeating_command_block chain_command_block frosted_ice magma nether_wart_block
red_nether_brick bone_block structure_void observer'''.split()
JAVA_IDS += [d + '_shulker_box' for d in DYES]
JAVA_IDS += [d + '_glazed_terracotta' for d in DYES]
JAVA_IDS += ['concrete', 'concrete_powder', 'unknown', 'unknown', 'structure_block']
assert JAVA_IDS[219] == 'white_shulker_box' and JAVA_IDS[251] == 'concrete', (JAVA_IDS[219], JAVA_IDS[251])

STONE_VARIANTS = ['stone', 'granite', 'smooth_granite', 'diorite', 'smooth_diorite', 'andesite', 'smooth_andesite']
SLAB_VARIANTS = ['smooth_stone', 'sandstone', 'oak', 'cobblestone', 'brick', 'stone_brick', 'nether_brick', 'quartz']
FLOWER_VARIANTS = ['poppy', 'blue_orchid', 'allium', 'houstonia', 'tulip_red', 'tulip_orange', 'tulip_white',
                   'tulip_pink', 'oxeye']


def java_variant(name, data):
    """Return (name, variant) for a 1.12 id name and data value."""
    if name in ('wool', 'stained_glass', 'stained_glass_pane', 'stained_hardened_clay', 'carpet',
                'concrete', 'concrete_powder'):
        return name, DYES[data & 15]
    if name in ('planks', 'sapling', 'double_wooden_slab'):
        return name if name != 'double_wooden_slab' else 'planks', WOODS[data & 7 if (data & 7) < 6 else 0]
    if name == 'wooden_slab':
        w = WOODS[(data & 7) if (data & 7) < 6 else 0]
        return w + '_slab', ('#top' if data & 8 else '')
    if name in ('log', 'leaves'):
        return name, WOODS[data & 3]
    if name in ('log2', 'leaves2'):
        return name, WOODS[4 + (data & 1)]
    if name == 'stone':
        return name, STONE_VARIANTS[data if data < 7 else 0]
    if name == 'sand':
        return name, 'red' if data == 1 else ''
    if name == 'dirt':
        return name, ['', 'coarse', 'podzol'][data if data < 3 else 0]
    if name == 'stonebrick':
        return name, ['', 'mossy', 'cracked', 'chiseled'][data & 3]
    if name == 'prismarine':
        return name, ['', 'bricks', 'dark'][data if data < 3 else 0]
    if name == 'red_flower':
        return name, FLOWER_VARIANTS[data if data < 9 else 0]
    if name in ('stone_slab', 'double_stone_slab'):
        mat = SLAB_VARIANTS[data & 7]
        if name == 'double_stone_slab':
            return mat + '_double_slab', ''
        return mat + '_slab', ('#top' if data & 8 else '')
    if name in ('stone_slab2', 'purpur_slab'):
        mat = 'red_sandstone' if name == 'stone_slab2' else 'purpur'
        return mat + '_slab', ('#top' if data & 8 else '')
    if name in ('double_stone_slab2', 'purpur_double_slab'):
        return ('red_sandstone' if name == 'double_stone_slab2' else 'purpur') + '_double_slab', ''
    if name == 'cobblestone_wall':
        return name, 'mossy_cobblestone' if data == 1 else ''
    if name == 'fence':
        return name, 'oak'
    if name == 'monster_egg':
        return name, ''
    return name, ''


# --------------------------------------------------------------------------------------------
# Bedrock states -> variant

BEDROCK_VARIANT_KEYS = ['color', 'wood_type', 'old_log_type', 'new_log_type', 'old_leaf_type', 'new_leaf_type',
                        'stone_type', 'sand_type', 'stone_slab_type', 'stone_slab_type_2', 'stone_slab_type_3',
                        'stone_slab_type_4', 'stone_brick_type', 'prismarine_block_type', 'dirt_type',
                        'flower_type', 'wall_block_type', 'sand_stone_type', 'chisel_type']
BEDROCK_RENAME = {'grass': 'grass', 'brick_block': 'brick_block', 'seaLantern': 'sea_lantern',
                  'stonebrick': 'stonebrick', 'wooden_slab': 'wooden_slab', 'double_wooden_slab': 'planks',
                  'tallgrass': 'tallgrass', 'concretePowder': 'concrete_powder', 'concretepowder': 'concrete_powder',
                  'lit_redstone_lamp': 'lit_redstone_lamp', 'unpowered_comparator': 'unpowered_comparator',
                  'normal_stone_stairs': 'stone_stairs', 'stone_stairs': 'cobblestone_stairs',
                  'wood': 'log', 'mossy_stone_brick_stairs': 'mossy_stone_brick_stairs'}


def bedrock_variant(name, states):
    name = name.replace('minecraft:', '')
    name = BEDROCK_RENAME.get(name, name)
    v = ''
    for k in BEDROCK_VARIANT_KEYS:
        if k in states:
            v = str(states[k])
            break
    if name == 'log2':
        v = {'acacia': 'acacia', 'dark_oak': 'dark_oak'}.get(v, v)
    if name in ('leaves2',):
        v = {'acacia': 'acacia', 'dark_oak': 'dark_oak'}.get(v, v)
    if name == 'sand':
        v = 'red' if v == 'red' else ''
    if name == 'dirt':
        v = 'coarse' if v == 'coarse' else ''
    if name == 'stonebrick':
        v = 'mossy' if v == 'mossy' else ''
    if name == 'prismarine':
        v = {'bricks': 'bricks', 'dark': 'dark'}.get(v, '')
    if 'slab' in name:
        if name == 'wooden_slab':
            name = (v or 'oak') + '_slab'
            v = ''
        elif name.startswith('stone_slab') or name.startswith('double_stone_slab'):
            mat = v or 'smooth_stone'
            name = mat + ('_double_slab' if name.startswith('double') else '_slab')
            v = ''
        if states.get('top_slot_bit') in (1, True):
            v = v + '#top'
    if name == 'cobblestone_wall':
        v = v if v and v != 'cobblestone' else ''
    if name in ('fence',):
        v = v or 'oak'
    return name, v


# --------------------------------------------------------------------------------------------

SHAPES = ['full', 'slab_b', 'slab_t', 'post', 'small']
KINDS = ['skip', 'solid', 'trans', 'overlay']


class Palette:
    """Global registry of drawable block types. Index 0 is always air."""

    def __init__(self):
        self.keys = []
        self.index = {}
        self.rgb = []
        self.side = []
        self.kind = []
        self.shape = []
        self.alpha = []
        self.blend = []
        self.glow = []
        self.built = []
        self.add('air', '')

    def add(self, name, variant):
        key = (name, variant)
        i = self.index.get(key)
        if i is not None:
            return i
        rgb, kind, shape, extra = describe(name, variant)
        i = len(self.keys)
        self.index[key] = i
        self.keys.append(key)
        self.rgb.append(rgb)
        self.side.append(extra.get('side', rgb))
        self.kind.append(KINDS.index(kind))
        self.shape.append(SHAPES.index(shape))
        self.alpha.append(extra.get('alpha', 1.0))
        self.blend.append(extra.get('blend', 1.0))
        self.glow.append(bool(extra.get('glow', False)))
        base = name.replace('minecraft:', '')
        self.built.append(built_weight(base))
        return i

    def arrays(self):
        return dict(
            rgb=np.array(self.rgb, dtype=np.float32),
            side=np.array(self.side, dtype=np.float32),
            kind=np.array(self.kind, dtype=np.uint8),
            shape=np.array(self.shape, dtype=np.uint8),
            alpha=np.array(self.alpha, dtype=np.float32),
            blend=np.array(self.blend, dtype=np.float32),
            glow=np.array(self.glow, dtype=bool),
            built=np.array(self.built, dtype=np.float32),
        )

    def label(self, i):
        n, v = self.keys[i]
        v = v.replace('#top', '')
        return (v + ' ' + n if v and v not in n else n).replace('_', ' ').strip()


def java_lut(palette):
    """LUT mapping (id << 4 | data) -> palette index for 1.12 worlds (ids 0..255)."""
    lut = np.zeros(4096 * 16, dtype=np.uint16)
    for bid, name in enumerate(JAVA_IDS):
        for data in range(16):
            n, v = java_variant(name, data)
            lut[(bid << 4) | data] = palette.add(n, v)
    for bid in range(len(JAVA_IDS), 4096):
        lut[bid << 4:(bid << 4) + 16] = palette.add('unknown', '')
    return lut
