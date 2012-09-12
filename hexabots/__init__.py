#!/usr/bin/python

import math, copy, random, sys
import direct.directbase.DirectStart
from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import BitMask32, GeomNode, VBase4, NodePath, Point2

HEX_DIAM = 10
BOARD_X = 160
BOARD_Y = 160
SQRT_3 = math.sqrt(3)
RAD_TO_DEG = 180.0 / math.pi
DEG_TO_RAD = 1.0 / RAD_TO_DEG
# tan(INTERIOR_ANGLE / 2) * sin(IDEAL_AZIMUTH) == 1
IDEAL_AZIMUTH = math.asin(1.0 / math.tan(60.0 * DEG_TO_RAD)) * RAD_TO_DEG

def board_coordinates(x, y, z):
    board_x = 0.75 * HEX_DIAM * x
    board_y = HEX_DIAM * SQRT_3 / 2 * y + (x % 2 * 0.5 * HEX_DIAM * SQRT_3 / 2)
    return (board_x, board_y, z)

def get_adjacent(terrain, x, y):
    if x % 2 == 0:
        coords = [(x-1, y), (x, y+1), (x+1, y), (x+1, y-1), (x, y-1), (x-1, y-1)]
    else:
        coords = [(x-1, y+1), (x, y+1), (x+1, y+1), (x+1, y), (x, y-1), (x-1, y)]
    adjacent = []
    for coord in coords:
        if coord[0] < 0 or coord[1] < 0:
            adjacent.append(None)
        elif coord[0] >= terrain.size_x or coord[1] >= terrain.size_y:
            adjacent.append(None)
        else:
            adjacent.append(terrain.rows[coord[0]][coord[1]])
    return adjacent

def tile_distance_squared(tile1, tile2):
    (x1, y1, z1) = board_coordinates(tile1.x, tile1.y, 0)
    (x2, y2, z2) = board_coordinates(tile2.x, tile2.y, 0)
    vector = Point2(x1, y1) - Point2(x2, y2)
    return vector.lengthSquared()

def find_nearby(terrain, x, y, distance):
    nearby = []
    distance_squared = (distance * HEX_DIAM) ** 2.0
    (pos_x, pos_y, pos_z) = board_coordinates(x, y, 0)
    for x2, row in enumerate(terrain.rows):
        for y2, tile in enumerate(row):
            (pos_x2, pos_y2, pos_z2) = board_coordinates(tile.x, tile.y, 0)
            vector = Point2(pos_x, pos_y) - Point2(pos_x2, pos_y2)
            length_squared = vector.lengthSquared()
            if length_squared <= distance_squared:
                nearby.append(tile)
    return nearby


class Mouse(DirectObject):
    def __init__(self, app):
        self.app = app
        self.init_collide()
        self.has_mouse = None
        self.prev_pos = None
        self.pos = None
        self.drag_start = None
        self.hovered_object = None
        self.button2 = False
        self.mouseTask = taskMgr.add(self.mouse_task, 'mouseTask')
        self.task = None
        self.accept('mouse1', self.mouse1)
        self.accept('mouse1-up', self.mouse1_up)
        self.accept('mouse2', self.rotateCamera)
        self.accept('mouse2-up', self.stopCamera)
        self.accept('wheel_up', self.zoomIn)
        self.accept('wheel_down', self.zoomOut)

    def init_collide(self):
        from pandac.PandaModules import CollisionTraverser, CollisionNode
        from pandac.PandaModules import CollisionHandlerQueue, CollisionRay
        self.cTrav = CollisionTraverser('MousePointer')
        self.cQueue = CollisionHandlerQueue()
        self.cNode = CollisionNode('MousePointer')
        self.cNodePath = base.camera.attachNewNode(self.cNode)
        self.cNode.setFromCollideMask(GeomNode.getDefaultCollideMask())
        self.cRay = CollisionRay()
        self.cNode.addSolid(self.cRay)
        self.cTrav.addCollider(self.cNodePath, self.cQueue)

    def find_object(self):
        if self.app.world.nodePath:
            self.cRay.setFromLens(base.camNode, self.pos.getX(), self.pos.getY())
            self.cTrav.traverse(self.app.world.terrain.nodePath)
            if self.cQueue.getNumEntries() > 0:
                self.cQueue.sortEntries()
                return self.cQueue.getEntry(0).getIntoNodePath()
        return None

    def mouse_task(self, task):
        action = task.cont
        self.has_mouse = base.mouseWatcherNode.hasMouse()
        if self.has_mouse:
            self.pos = base.mouseWatcherNode.getMouse()
            if self.prev_pos:
                self.delta = self.pos - self.prev_pos
            else:
                self.delta = None
            if self.task:
                action = self.task(task)
        else:
            self.pos = None
        if self.pos:
            self.prev_pos = Point2(self.pos.getX(), self.pos.getY())
        return action

    def hover(self, task):
        if self.hovered_object:
            self.hovered_object.unhover()
            self.hovered_object = None
        if self.button2:
            self.camera_drag()
        hovered_nodePath = self.find_object()
        if hovered_nodePath:
            tile = hovered_nodePath.findNetTag('tile')
            if not tile.isEmpty():
                tag = tile.getTag('tile')
                coords = tag.split(',')
                (x, y) = [int(n) for n in coords]
                self.hovered_object = self.app.world.terrain.rows[x][y]
                self.hovered_object.hover()
            character = hovered_nodePath.findNetTag('char')
            if not character.isEmpty():
                tag = character.getTag('char')
                (team_index, char_id) = [int(n) for n in tag.split(',')]
                self.hovered_object = self.app.world.teams[team_index].characters_dict[char_id]
                self.hovered_object.hover()
        return task.cont

    def mouse1(self):
        self.app.state.request('mouse1')

    def mouse1_up(self):
        self.app.state.request('mouse1-up')

    def camera_drag(self):
        if self.delta:
            old_heading = base.camera.getH()
            new_heading = old_heading - self.delta.getX() * 180
            base.camera.setH(new_heading % 360)
            old_pitch = base.camera.getP()
            new_pitch = old_pitch + self.delta.getY() * 90
            new_pitch = max(-90, min(0, new_pitch))
            base.camera.setP(new_pitch)

    def rotateCamera(self):
        self.button2 = True

    def stopCamera(self):
        self.button2 = False

    def zoomIn(self):
        lens = base.cam.node().getLens()
        size = lens.getFilmSize()
        lens.setFilmSize(size / 1.2)

    def zoomOut(self):
        lens = base.cam.node().getLens()
        size = lens.getFilmSize()
        lens.setFilmSize(size * 1.2)


class Team(DirectObject):
    def __init__(self, world, index, name, color):
        self.world = world
        self.index = index
        self.name = name
        self.color = color
        self.characters = []
        self.characters_dict = {}

    def add_character(self, x, y):
        character_id = random.randint(0, 256)
        while self.characters_dict.has_key(character_id):
            character_id = random.randint(0, 256)
        char = Character(self.world.terrain, self, character_id, x, y)
        self.characters.append(char)
        self.characters_dict[character_id] = char
        return char

    def delete_character(self, character_id):
        for i, char in enumerate(self.characters):
            if char == self.characters_dict[character_id]:
                char.nodePath.removeNode()
                del self.characters[i]
        del self.characters_dict[character_id]


class Character(DirectObject):
    def __init__(self, terrain, team, id, x, y):
        self.terrain = terrain
        self.team = team
        self.id = id
        self.x = x
        self.y = y
        self.CT = 0.0
        self.efficiency = 1.0
        self.is_dead = False
        self.tile = self.terrain.rows[x][y]
        self.height = self.tile.height
        self.color = self.team.color
        self.pending_action = None
        self.nodePath = None

    def init_nodepath(self):
        self.nodePath = loader.loadModel('models/character')
        self.nodePath.reparentTo(self.terrain.nodePath)
        self.nodePath.setColor(VBase4(*self.color))
        (pos_x, pos_y, pos_z) = board_coordinates(self.x, self.y, self.height)
        self.nodePath.setPos(pos_x, pos_y, pos_z)
        self.nodePath.setScale(5, 5, 5)
        self.nodePath.setTag('char', '%u,%u' % (self.team.index, self.id))

    def move_to(self, tile):
        self.tile = tile
        (self.x, self.y, self.height) = (tile.x, tile.y, tile.height)
        (pos_x, pos_y, pos_z) = board_coordinates(self.x, self.y, self.height)
        self.nodePath.setPos(pos_x, pos_y, pos_z)

    def hover(self):
        color = self.nodePath.getColor() * 1.5
        self.nodePath.setColor(color)

    def unhover(self):
        color = self.nodePath.getColor() / 1.5
        self.nodePath.setColor(color)

    def charge(self, time_delta):
        self.CT += time_delta * self.efficiency
        if self.CT > 1.0:
            self.CT = 1.0

    def set_action(self, action):
        self.pending_action = action
        self.CT -= self.pending_action.pre_cost()

    def do_action(self):
        self.pending_action.do()
        self.CT -= self.pending_action.post_cost()
        self.pending_action = None

    def damage(self, damage):
        self.efficiency -= damage
        if self.should_die():
            self.efficiency = 0.0

    def should_die(self):
        return bool(self.efficiency <= 0.0)

    def die(self):
        print self, 'died'
        self.is_dead = True
        self.nodePath.removeNode()

    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['nodePath'] = None
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)
        self.CT = random.random()


class Tile(DirectObject):
    def __init__(self, terrain, material, x, y, height):
        self.terrain = terrain
        self.material = material
        self.x = x
        self.y = y
        self.height = height
        self.adjacent = []
        self.nodePath = None

    def init_nodepath(self):
        self.nodePath = self.terrain.nodePath.attachNewNode('tile')
        cyl = loader.loadModel('models/tile-cyl').reparentTo(self.nodePath)
        cap = loader.loadModel('models/tile-cap').reparentTo(self.nodePath)
        if self.material == 'grass':
            new_color = VBase4(0, .7, 0, 1.0)
        elif self.material == 'stone':
            new_color = VBase4(.5, .5, .5, 1.0)
        if self.material == 'water':
            new_color = VBase4(0, 0, .7, 1.0)
        self.nodePath.setColor(new_color)
        (pos_x, pos_y, pos_z) = board_coordinates(self.x, self.y, 0)
        self.nodePath.setPos(pos_x, pos_y, pos_z)
        self.set_height(self.height)
        self.nodePath.setTag('tile', '%u,%u' % (self.x, self.y))

    def hover(self):
        self.terrain.hoveredTile = self
        color = self.nodePath.getColor() * 1.5
        self.nodePath.setColor(color)

    def unhover(self):
        self.terrain.hoveredTile = None
        color = self.nodePath.getColor() / 1.5
        self.nodePath.setColor(color)

    def set_height(self, new_height):
        self.height = round(new_height / 2.0) * 2
        self.nodePath.find('**/tile-cyl.egg').setSz(self.height)
        self.nodePath.find('**/tile-cap.egg').setZ(self.height - 1.0)

    def select(self):
        self.terrain.selectedTile = self

    def unselect(self):
        self.terrain.selectedTile = None

    def change_material(self, new_material):
        self.material = new_material
        if self.material == 'grass':
            new_color = VBase4(0, .7, 0, 1.0)
        elif self.material == 'stone':
            new_color = VBase4(.5, .5, .5, 1.0)
        if self.material == 'water':
            new_color = VBase4(0, 0, .7, 1.0)
        if self.terrain.hoveredTile == self:
            new_color *= 1.5
        self.nodePath.setColor(new_color)

    def get_inhabitants(self):
        characters = []
        for team in self.terrain.world.teams:
            for character in team.characters:
                if character.is_dead:
                    continue
                if (character.x, character.y) == (self.x, self.y):
                    characters.append(character)
        return characters

    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['nodePath'] = None
        safe_dict['adjacent'] = []
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)


class Terrain(DirectObject):
    def __init__(self, world):
        self.world = world
        self.rows = []
        self.hoveredTile = None
        self.selectedTile = None
        self.size_x = BOARD_X
        self.size_y = BOARD_Y
        self.nodePath = None

    def init_nodepath(self):
        self.nodePath = self.world.nodePath.attachNewNode('Terrain')
        for row in self.rows:
            for tile in row:
                tile.init_nodepath()

    def generate(self):
        for x in range(self.size_x):
            row = []
            for y in range(self.size_y):
                material = 'grass'
                height = 2
                tile = Tile(self, material, x, y, height)
                row.append(tile)
            self.rows.append(row)
        for x in range(self.size_x):
            for y in range(self.size_y):
                self.rows[x][y].adjacent = get_adjacent(self, x, y)

    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['hoveredTile'] = None
        safe_dict['selectedTile'] = None
        safe_dict['nodePath'] = None
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)
        for x in range(self.size_x):
            for y in range(self.size_y):
                self.rows[x][y].adjacent = get_adjacent(self, x, y)


class World(DirectObject):
    def __init__(self):
        base.setBackgroundColor(0, 0.2, 0.5)
        self.init_terrain()
        self.init_teams()
        self.position_camera()
        self.nodePath = None

    def init_nodepath(self):
        self.nodePath = render.attachNewNode('World')
        self.init_lights()
        self.init_camera()
        self.terrain.init_nodepath()
        for team in self.teams:
            for character in team.characters:
                character.init_nodepath()

    def clear(self):
        if self.nodePath:
            self.nodePath.removeNode()

    def generate(self):
        self.terrain.generate()
        self.teams = [
                Team(self, 0, 'Team 1', (0.1, 0.1, 0.1, 1.0)),
                Team(self, 1, 'Team 2', (0.9, 0.9, 0.9, 1.0)),
        ]
        self.teams[0].add_character(0, 0)
        self.teams[1].add_character(self.terrain.size_x - 1, self.terrain.size_y - 1)

    def init_lights(self):
        from pandac.PandaModules import AmbientLight, DirectionalLight
        from pandac.PandaModules import ShadeModelAttrib
        # Set flat shading
        flatShade = ShadeModelAttrib.make(ShadeModelAttrib.MFlat)
        self.nodePath.setAttrib(flatShade)
        # Create directional light
        dlight1 = DirectionalLight('dlight1')
        dlight1.setColor(VBase4(1.0, 1.0, 1.0, 1.0))
        dlnp1 = self.nodePath.attachNewNode(dlight1)
        dlnp1.setHpr(-10, -30, 0)
        self.nodePath.setLight(dlnp1)
        # Create second directional light
        dlight2 = DirectionalLight('dlight2')
        dlight2.setColor(VBase4(0.0, 0.1, 0.2, 1.0))
        dlnp2 = self.nodePath.attachNewNode(dlight2)
        dlnp2.setHpr(170, 0, 0)
        self.nodePath.setLight(dlnp2)
        # Create ambient light
        alight = AmbientLight('alight')
        alight.setColor(VBase4(0.3, 0.3, 0.3, 1.0))
        alnp = self.nodePath.attachNewNode(alight)
        self.nodePath.setLight(alnp)

    def init_camera(self):
        from pandac.PandaModules import OrthographicLens
        lens = OrthographicLens()
        # TODO: Find real aspect ratio
        lens.setAspectRatio(4.0/3.0)
        lens.setNear(-1000)
        base.cam.node().setLens(lens)
        base.camera.setHpr(60, 0 - IDEAL_AZIMUTH, 0)

    def position_camera(self):
        width = math.sqrt((0.75 * HEX_DIAM * self.terrain.size_x) ** 2 + (HEX_DIAM * SQRT_3 / 2 * self.terrain.size_y) ** 2)
        base.cam.node().getLens().setFilmSize(width)
        (pos_x, pos_y, pos_z) = board_coordinates(self.terrain.size_x * 0.5, self.terrain.size_y * 0.5, 0)
        base.camera.setPos(pos_x, pos_y, 10)

    def init_terrain(self):
        self.terrain = Terrain(self)

    def init_teams(self):
        self.teams = []

    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['nodePath'] = None
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)
        self.init_nodepath()
