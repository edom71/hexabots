#!/usr/bin/python

import cPickle, random, operator
from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import Point2, Point3
from direct.fsm import FSM
from direct.interval.IntervalGlobal import *
from direct.gui.DirectGui import *
from hexabots import World, Mouse, Tile, Character
from hexabots import HEX_DIAM, board_coordinates, find_nearby, tile_distance_squared


"""
Elements: ?
    Neutral (General Robotics)
    Earth (Titan Industries)
    Fire (Pyronetics, Inc.)
    Water (Wetworks Manufacturing)
    Lightning (Megajoule)
    Time (Cronodyne Corp.)

Terrain types:
    Rock
    Sand
    Grass
    Forest
    Tree
    Lava
    Shallow Water
    Deep Water
    Ice
    Snow

Movement modes:
    Flying (Fire)
        High energy consumption
        Moderate-to-high vertical movement
        Able to inhabit tiles with non-flying characters
        Able to move across any tile
    Hovering (Lightning)
        Moderate energy consumption
        Very low vertical movement
        Able to move across land or water
    Walking (Neutral)
        Low energy consumption
        Low vertical movement
        Able to move across land or shallow water
    Rolling (wheels/treads) (Earth)
        Low energy consumption
        Very low vertical movement
        Better than walking on sand and snow
        Worse than walking in forests
        Able to move across land
    Floating (boat) (Water)
        Low-to-moderate energy consumption
        Able to move across water
    Teleporation (Time)
        Very high energy consumption
        Very high vertical movement
        Able to move across any tile
"""


def cleanup():
    for team in app.world.teams:
        for character in team.characters:
            if not character.is_dead and character.should_die():
                character.die()

def game_over():
    teams_alive = []
    for team in app.world.teams:
        if not reduce(operator.and_, [c.is_dead for c in team.characters]):
            teams_alive.append(team)
    if len(teams_alive) == 1:
        app.winner = OnscreenText(text='%s wins!' % (teams_alive[0].name,), pos=(-0.9, -0.8), fg=(1.0, 1.0, 1.0, 1.0))
        return True
    return False

def charge(task):
    cleanup()
    if game_over():
        app.state.request('AwaitLoad')
        return task.done
    while True:
        for team in app.world.teams:
            for character in team.characters:
                if character.is_dead:
                    continue
                character.charge(0.001)
                if character.CT >= 1.0:
                    if character.team.name == 'Team 1':
                        app.state.request('Team1', character)
                        return task.done
                    if character.team.name == 'Team 2':
                        app.state.request('Team2', character)
                        return task.done
    return task.cont

def find_opponent(teams, character):
    least_distance = 999999999
    closest_opponent = None
    for team in teams:
        if team == character.team:
            continue
        for other_character in team.characters:
            if other_character.is_dead:
                continue
            distance = tile_distance_squared(other_character.tile, character.tile)
            if distance < least_distance:
                least_distance = distance
                closest_opponent = other_character
    return closest_opponent


class Move(object):
    def __init__(self, mover, tile):
        self.mover = mover
        self.tile = tile

    def pre_cost(self):
        return 0.0

    def post_cost(self):
        import math
        distance = math.sqrt(tile_distance_squared(self.mover.tile, self.tile))
        return distance / HEX_DIAM / 3.5

    def do(self):
        inhabitants = self.tile.get_inhabitants()
        if inhabitants:
            # TODO: Maybe move somewhere else?
            app.state.demand('Charge')
        else:
            to_coords = Point3(*board_coordinates(self.tile.x, self.tile.y, self.tile.height))
            i_move = LerpPosInterval(self.mover.nodePath, 0.5, to_coords)
            i_finish = Func(self.post_do)
            i_sequence = Sequence(i_move, i_finish)
            i_sequence.start()

    def post_do(self):
        self.mover.move_to(self.tile)
        app.state.request('Charge')


class Attack(object):
    def __init__(self, attacker, target):
        self.attacker = attacker
        self.target = target

    def pre_cost(self):
        return 0.2

    def post_cost(self):
        return 0.2

    def do(self):
        # TODO: Make sure target is still in range
        from_coords = Point3(*board_coordinates(self.attacker.x, self.attacker.y, self.attacker.height))
        to_coords = Point3(*board_coordinates(self.target.x, self.target.y, self.target.height))
        i_move_to = LerpPosInterval(self.attacker.nodePath, 0.1, to_coords, blendType='easeIn')
        i_move_from = LerpPosInterval(self.attacker.nodePath, 0.1, from_coords, blendType='easeOut')
        i_finish = Func(self.post_do)
        i_sequence = Sequence(i_move_to, i_move_from, i_finish)
        i_sequence.start()

    def post_do(self):
        self.target.damage(0.2)
        app.state.request('Charge')


class PlayState(FSM.FSM):
    def __init__(self, name):
        FSM.FSM.__init__(self, name)
        self.character = None
        self.movement_candidates = []

    def enterAwaitLoad(self):
        app.welcome = OnscreenText(text='Press L to load a level', pos=(-0.9, -0.9), fg=(1.0, 1.0, 1.0, 1.0))

    def exitAwaitLoad(self):
        app.welcome.destroy()
        if app.winner:
            app.winner.destroy()

    def enterCharge(self):
        taskMgr.add(charge, 'charge')

    def exitCharge(self):
        taskMgr.remove('charge')

    def filterCharge(self, request, args):
        if request in ['Team1', 'Team2']:
            (character,) = args
            if character.pending_action:
                return ('PlayAnim', character.do_action)
            return request
        if request == 'AwaitLoad':
            return request

    def enterPlayAnim(self, action):
        action()

    def exitPlayAnim(self):
        pass

    def enterTeam1(self, character):
        app.mouse.task = app.mouse.hover
        self.character = character
        self.movement_candidates = find_nearby(app.world.terrain, character.x, character.y, 3.5)
        self.attack_candidates = find_nearby(app.world.terrain, character.x, character.y, 1.0)
        for tile in self.movement_candidates:
            tile.nodePath.setColor(0.5, 0.6, 1.0)
            if app.world.terrain.hoveredTile == tile:
                tile.nodePath.setColor(0.75, 0.9, 1.5)
        for tile in self.attack_candidates:
            tile.nodePath.setColor(1.0, 0.6, 0.5)
            if app.world.terrain.hoveredTile == tile:
                tile.nodePath.setColor(1.5, 0.9, 0.75)

    def exitTeam1(self):
        app.mouse.task = None
        app.mouse.hovered_object.unhover()
        app.mouse.hovered_object = None
        for tile in self.movement_candidates:
            tile.change_material(tile.material)
        self.movement_candidates = None
        self.attack_candidates = None
        self.character = None

    def filterTeam1(self, request, args):
        if request == 'AwaitLoad':
            return 'AwaitLoad'
        character = self.character
        if request == 'mouse1':
            selected = app.mouse.hovered_object
            if not selected:
                return None
            if isinstance(selected, Tile):
                if selected in self.movement_candidates and not selected.get_inhabitants():
                    character.set_action(Move(character, selected))
                    return 'Charge'
            elif isinstance(selected, Character):
                if selected.team != character.team and selected.tile in self.attack_candidates:
                    character.set_action(Attack(character, selected))
                    return 'Charge'
        return None

    def enterTeam2(self, character):
        player = find_opponent(app.world.teams, character)
        self.movement_candidates = find_nearby(app.world.terrain, character.x, character.y, 3.5)
        self.attack_candidates = find_nearby(app.world.terrain, character.x, character.y, 1.0)
        if player.tile in self.attack_candidates:
            character.set_action(Attack(character, player))
        else:
            shortest_distance = 10000000
            closest_tile = None
            for tile in self.movement_candidates:
                if tile.get_inhabitants():
                    continue
                vector = Point2(tile.x, tile.y) - Point2(player.x, player.y)
                distance = vector.lengthSquared()
                if distance < shortest_distance and distance > 0:
                    shortest_distance = distance
                    closest_tile = tile
            character.set_action(Move(character, closest_tile))
        self.demand('Charge')

    def exitTeam2(self):
        for tile in self.movement_candidates:
            tile.change_material(tile.material)
        self.movement_candidates = None
        self.attack_candidates = None
        self.character = None


class PlayMouse(Mouse):
    pass


class PlayApp(DirectObject):
    def __init__(self):
        base.disableMouse()
        self.world = World()
        self.mouse = PlayMouse(self)
        self.state = PlayState('state')
        self.accept('l', self.load_world)
        self.accept('L', self.load_world)
        self.welcome = None
        self.winner = None

    def load_world(self):
        def load(filename):
            self.delete_world()
            F = open(filename, 'rb')
            self.world = cPickle.load(F)
            F.close()
            entry.destroy()
            self.world.position_camera()
            self.state.request('Charge')
        self.welcome.removeNode()
        self.state.request('AwaitLoad')
        entry = DirectEntry(text='', scale=0.05, command=load,
                initialText='level.hm', focus=1)

    def delete_world(self):
        self.world.clear()

app = PlayApp()
app.state.request('AwaitLoad')
run()
