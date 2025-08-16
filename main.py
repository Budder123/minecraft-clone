import sys

from panda3d.core import AmbientLight, DirectionalLight
from panda3d.core import TextNode, NodePath
from panda3d.core import VBase4
from panda3d.core import WindowProperties
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText

from world import World
from player import Player


class VoxelGame(ShowBase):
    def __init__(self):
        super().__init__()

        # Set up the world
        self.world = World(self)
        self.generate_initial_chunks()

        # Set up the player
        self.player = Player(self, self.world)

        # Set up the window
        props = WindowProperties()
        props.set_cursor_hidden(True)
        props.set_mouse_mode(WindowProperties.M_RELATIVE)
        self.win.request_properties(props)

        # Set up lighting
        self.setup_lighting()

        # Add a crosshair
        self.crosshair = OnscreenImage(
            image='textures/crosshair.png',  # I'll need to create this texture
            pos=(0, 0, 0),
            scale=0.05
        )
        self.crosshair.set_transparency(True)

        # Add instructions
        self.instructions = OnscreenText(
            text="[WASD] - Move\n[Space] - Jump\n[Mouse] - Look\n[Left-Click] - Break Block\n[Right-Click] - Place Block\n[ESC] - Exit",
            pos=(-1.3, 0.9),
            scale=0.05,
            align=TextNode.ALeft
        )

        # Handle closing the window
        self.accept('escape', sys.exit)

    def setup_lighting(self):
        # Ambient light
        ambient_light = AmbientLight('ambient_light')
        ambient_light.set_color(VBase4(0.5, 0.5, 0.5, 1))
        self.ambient_light_np = self.render.attach_new_node(ambient_light)
        self.render.set_light(self.ambient_light_np)

        # Directional light
        dir_light = DirectionalLight('dir_light')
        dir_light.set_color(VBase4(0.8, 0.8, 0.8, 1))
        self.dir_light_np = self.render.attach_new_node(dir_light)
        self.dir_light_np.set_hpr(0, -60, 0)
        self.render.set_light(self.dir_light_np)

    def generate_initial_chunks(self):
        for x in range(-2, 3):
            for y in range(-2, 3):
                self.world.generate_chunk(x, y)


if __name__ == '__main__':
    app = VoxelGame()
    app.run()
