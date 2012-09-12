#!/usr/bin/python

import cPickle
from direct.showbase.DirectObject import DirectObject
from direct.fsm import FSM
from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import *
from pandac.PandaModules import GeomNode, Point2
from hexabots import World, Mouse, Tile, Character


class EditState(FSM.FSM):
    def __init__(self, name):
        FSM.FSM.__init__(self, name)
        self.defaultTransitions = {
                'Height' : [ 'HeightDrag', 'Material', 'Character' ],
                'HeightDrag' : [ 'Height' ],
                'Material' : [ 'MaterialDrag', 'Height', 'Character' ],
                'MaterialDrag' : [ 'Material' ],
                'Character' : [ 'CharacterDrag', 'Height', 'Material' ],
                'CharacterDrag' : [ 'Character' ],
                }

    nextState = {
            ('Height', 'Material'): 'Material',
            ('Height', 'Character'): 'Character',
            ('Material', 'Height'): 'Height',
            ('Material', 'Character'): 'Character',
            ('Character', 'Height'): 'Height',
            ('Character', 'Material'): 'Material',
            ('Height', 'mouse1'): 'HeightDrag',
            ('HeightDrag', 'mouse1-up'): 'Height',
            ('Material', 'mouse1'): 'MaterialDrag',
            ('MaterialDrag', 'mouse1-up'): 'Material',
            ('Character', 'mouse1'): 'CharacterDrag',
            ('CharacterDrag', 'mouse1-up'): 'Character',
            }

    def defaultFilter(self, request, args):
        key = (self.state, request)
        return self.nextState.get(key)

    def enterHeight(self):
        app.mouse.task = app.mouse.hover

    def exitHeight(self):
        app.mouse.task = None

    def enterHeightDrag(self):
        app.selected_object = app.mouse.hovered_object
        if app.selected_object:
            app.selected_object.old_height = app.selected_object.height
            app.mouse.drag_start = Point2(app.mouse.pos.getX(), app.mouse.pos.getY())
            app.mouse.task = app.mouse.height_drag

    def exitHeightDrag(self):
        if app.selected_object:
            del app.selected_object.old_height
            app.selected_object = None
            app.mouse.drag_start = None
            app.mouse.task = None

    def enterMaterial(self):
        app.mouse.task = app.mouse.hover

    def exitMaterial(self):
        app.mouse.task = None

    def enterMaterialDrag(self):
        app.selected_object = app.mouse.hovered_object
        if app.selected_object:
            app.mouse.drag_start = Point2(app.mouse.pos.getX(), app.mouse.pos.getY())
            app.mouse.task = app.mouse.material_drag

    def exitMaterialDrag(self):
        if app.selected_object:
            app.selected_object = None
            app.mouse.drag_start = None
            app.mouse.task = None

    def enterCharacter(self):
        app.mouse.task = app.mouse.hover

    def exitCharacter(self):
        app.mouse.task = None

    def enterCharacterDrag(self):
        app.selected_object = app.mouse.hovered_object
        if app.selected_object:
            app.mouse.drag_start = Point2(app.mouse.pos.getX(), app.mouse.pos.getY())
            if isinstance(app.selected_object, Tile):
                coords = (app.selected_object.x, app.selected_object.y)
                inhabitants = app.world.terrain.rows[coords[0]][coords[1]].get_inhabitants()
                if inhabitants:
                    for char in inhabitants:
                        app.world.teams[char.team.index].delete_character(char.id)
                else:
                    char = app.world.teams[team_mode[0]].add_character(*coords)
                    if char:
                        char.init_nodepath()
            app.mouse.task = app.mouse.character_drag

    def exitCharacterDrag(self):
        if app.selected_object:
            app.selected_object = None
            app.mouse.drag_start = None
            app.mouse.task = None


class EditMouse(Mouse):

    def height_drag(self, task):
        if not isinstance(self.app.selected_object, Tile):
            return task.cont
        drag_delta = self.pos - self.drag_start
        new_height = self.app.selected_object.old_height + drag_delta.getY() * 100
        new_height = max(2, new_height)
        self.app.selected_object.set_height(new_height)
        inhabitants = self.app.selected_object.get_inhabitants()
        for character in inhabitants:
            character.move_to(self.app.selected_object)
        return task.cont

    def material_drag(self, task):
        if not isinstance(self.app.selected_object, Tile):
            return task.cont
        self.hover(task)
        if not isinstance(self.hovered_object, Tile):
            return task.cont
        self.app.selected_object = self.hovered_object
        if self.app.selected_object:
            self.app.selected_object.change_material(material[0])
        return task.cont

    def character_drag(self, task):
        if not isinstance(self.app.selected_object, Character):
            return task.cont
        self.hover(task)
        if not isinstance(self.hovered_object, Tile):
            return task.cont
        inhabitants = self.hovered_object.get_inhabitants()
        if not inhabitants:
            self.app.selected_object.move_to(self.hovered_object)
        return task.cont



mouse_mode = ['Height']
def set_mouse_mode(status=None):
    new_state = mouse_mode[0]
    try:
        app.state.request(new_state)
    except NameError:
        pass

material = ['grass']
def set_material(status=None):
    pass

team_mode = [0]
def set_team_mode(status=None):
    pass

class EditApp(DirectObject):
    def __init__(self):
        base.disableMouse()
        self.selected_object = None
        self.init_mouse()
        self.state = EditState('state')
        self.world = World()
        self.accept('c', self.generate_world)
        self.accept('s', self.save_world)
        self.accept('l', self.load_world)
        self.accept('d', self.delete_world)
        self.init_buttons()

    def init_buttons(self):
        mode_buttons = [
                DirectRadioButton(text='Height', variable=mouse_mode,
                        value=['Height'], scale=0.05, pos=(0.0, 0, -0.9),
                        command=set_mouse_mode),
                DirectRadioButton(text='Material', variable=mouse_mode,
                        value=['Material'], scale=0.05, pos=(0.25, 0, -0.9),
                        command=set_mouse_mode),
                DirectRadioButton(text='Character', variable=mouse_mode,
                        value=['Character'], scale=0.05, pos=(0.75, 0, -0.9),
                        command=set_mouse_mode),
        ]
        for button in mode_buttons:
            button.setOthers(mode_buttons)
        material_buttons = [
                DirectRadioButton(text='Grass', variable=material,
                        value=['grass'], scale=0.05, pos=(0.5, 0, -0.7),
                        command=set_material),
                DirectRadioButton(text='Stone', variable=material,
                        value=['stone'], scale=0.05, pos=(0.5, 0, -0.8),
                        command=set_material),
                DirectRadioButton(text='Water', variable=material,
                        value=['water'], scale=0.05, pos=(0.5, 0, -0.9),
                        command=set_material),
        ]
        for button in material_buttons:
            button.setOthers(material_buttons)
        character_buttons = [
                DirectRadioButton(text='Team 1', variable=team_mode,
                        value=[0], scale=0.05, pos=(1.0, 0, -0.8),
                        command=set_team_mode),
                DirectRadioButton(text='Team 2', variable=team_mode,
                        value=[1], scale=0.05, pos=(1.0, 0, -0.9),
                        command=set_team_mode),
        ]
        for button in character_buttons:
            button.setOthers(character_buttons)

    def init_mouse(self):
        self.mouse = EditMouse(self)

    def generate_world(self):
        self.delete_world()
        self.world = World()
        self.world.generate()
        self.world.init_nodepath()
        self.world.position_camera()
        text = OnscreenText(text='World created.', pos=(-0.9, -0.9), fg=(1.0, 1.0, 1.0, 1.0))
        def fadeText(task):
            alpha = 1.0 - task.time * 6.0
            if alpha > 0:
                text.setAlphaScale(alpha)
                return task.cont
            else:
                text.removeNode()
                return task.done
        taskMgr.doMethodLater(1.0, fadeText, 'fade')

    def save_world(self):
        def save(filename):
            F = open(filename, 'wb')
            cPickle.dump(self.world, F, True)
            F.close()
            entry.destroy()
        entry = DirectEntry(text='', scale=0.05, command=save,
                initialText='level.hm', focus=1)

    def load_world(self):
        def load(filename):
            self.delete_world()
            F = open(filename, 'rb')
            self.world = cPickle.load(F)
            F.close()
            entry.destroy()
            self.world.position_camera()
        entry = DirectEntry(text='', scale=0.05, command=load,
                initialText='level.hm', focus=1)

    def delete_world(self):
        self.world.clear()

app = EditApp()
app.state.request('Height')
run()
