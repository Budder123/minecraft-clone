from panda3d.core import VBase3, Point3
from panda3d.core import BitMask32
from panda3d.core import CollisionNode, CollisionRay, CollisionTraverser, CollisionHandlerQueue

from panda3d.core import LineSegs


class Player:
    def __init__(self, base, world):
        self.base = base
        self.world = world
        self.camera = self.base.camera
        self.render = self.base.render

        # Block interaction
        self.setup_interaction()

        # Player properties
        self.height = 1.8
        self.speed = 10
        self.jump_height = 1.2

        # Movement state
        self.velocity = VBase3(0, 0, 0)
        self.is_jumping = False

        # Player position
        self.player_node = self.render.attach_new_node("player")
        self.player_node.set_pos(8, 8, 80) # Start in the middle of a chunk
        self.camera.reparent_to(self.player_node)
        self.camera.set_pos(0, 0, self.height)

        # Mouse control
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_mouse_initialized = False

        # Input handling
        self.key_map = {
            "w": False, "s": False, "a": False, "d": False,
            "space": False
        }
        self.setup_controls()

        # Add update task
        self.base.task_mgr.add(self.update, "player_update")

    def setup_controls(self):
        self.base.accept("w", self.set_key, ["w", True])
        self.base.accept("w-up", self.set_key, ["w", False])
        self.base.accept("s", self.set_key, ["s", True])
        self.base.accept("s-up", self.set_key, ["s", False])
        self.base.accept("a", self.set_key, ["a", True])
        self.base.accept("a-up", self.set_key, ["a", False])
        self.base.accept("d", self.set_key, ["d", True])
        self.base.accept("d-up", self.set_key, ["d", False])
        self.base.accept("space", self.set_key, ["space", True])
        self.base.accept("space-up", self.set_key, ["space", False])
        self.base.accept("mouse1", self.break_block)
        self.base.accept("mouse3", self.place_block)

    def set_key(self, key, value):
        self.key_map[key] = value

    def setup_interaction(self):
        self.picker_ray = CollisionRay()
        self.picker_node = CollisionNode('mouseRay')
        self.picker_np = self.camera.attach_new_node(self.picker_node)
        self.picker_node.add_solid(self.picker_ray)
        self.picker_traverser = CollisionTraverser()
        self.picker_queue = CollisionHandlerQueue()
        self.picker_traverser.add_collider(self.picker_np, self.picker_queue)

        # Highlight cube
        self.highlight_node = self.render.attach_new_node("highlight")
        ls = LineSegs()
        ls.set_thickness(2)
        ls.set_color(0, 0, 0, 1)
        ls.move_to(0, 0, 0)
        ls.draw_to(1, 0, 0)
        ls.draw_to(1, 1, 0)
        ls.draw_to(0, 1, 0)
        ls.draw_to(0, 0, 0)
        ls.move_to(0, 0, 1)
        ls.draw_to(1, 0, 1)
        ls.draw_to(1, 1, 1)
        ls.draw_to(0, 1, 1)
        ls.draw_to(0, 0, 1)
        ls.move_to(1, 0, 0)
        ls.draw_to(1, 0, 1)
        ls.move_to(1, 1, 0)
        ls.draw_to(1, 1, 1)
        ls.move_to(0, 1, 0)
        ls.draw_to(0, 1, 1)
        node = ls.create()
        self.highlight_node.attach_new_node(node)
        self.highlight_node.hide()

    def update(self, task):
        # Block highlighting
        self.picker_ray.set_from_lens(self.base.camNode, 0, 0)
        self.picker_traverser.traverse(self.render)
        if self.picker_queue.get_num_entries() > 0:
            self.picker_queue.sort_entries()
            entry = self.picker_queue.get_entry(0)
            hit_pos = entry.get_surface_point(self.render)
            normal = entry.get_surface_normal(self.render)

            # Find the block position
            block_pos = hit_pos - normal * 0.5
            self.targeted_block = (int(block_pos.x), int(block_pos.y), int(block_pos.z))
            self.place_pos = self.targeted_block + normal

            self.highlight_node.set_pos(self.targeted_block)
            self.highlight_node.show()
        else:
            self.highlight_node.hide()
            self.targeted_block = None

        dt = globalClock.get_dt()

        # Mouse look
        if self.base.mouseWatcherNode.has_mouse():
            md = self.base.win.get_pointer(0)
            mouse_x = md.get_x()
            mouse_y = md.get_y()

            if self.is_mouse_initialized:
                delta_x = mouse_x - self.last_mouse_x
                delta_y = mouse_y - self.last_mouse_y

                # Update heading and pitch
                h = self.player_node.get_h() - delta_x * 20
                p = self.camera.get_p() - delta_y * 20
                p = max(-89, min(89, p)) # Clamp pitch
                self.player_node.set_h(h)
                self.camera.set_p(p)

            self.last_mouse_x = mouse_x
            self.last_mouse_y = mouse_y
            self.is_mouse_initialized = True

        # Movement
        move_direction = VBase3(0, 0, 0)
        if self.key_map["w"]:
            move_direction.y = 1
        if self.key_map["s"]:
            move_direction.y = -1
        if self.key_map["a"]:
            move_direction.x = -1
        if self.key_map["d"]:
            move_direction.x = 1

        move_direction.normalize()
        move_direction *= self.speed * dt

        # Apply movement relative to player's direction
        self.player_node.set_pos(self.player_node, move_direction)

        # Gravity
        self.velocity.z -= 20 * dt
        self.player_node.set_z(self.player_node.get_z() + self.velocity.z * dt)

        # Collisions
        self.handle_collisions()

        # Jumping
        if self.key_map["space"] and not self.is_jumping:
            self.is_jumping = True
            self.velocity.z = (2 * 9.81 * self.jump_height)**0.5

        return task.cont

    def handle_collisions(self):
        pos = self.player_node.get_pos()

        # Check ground collision
        ground_z = self.get_ground_height(pos.x, pos.y, pos.z)
        if pos.z < ground_z + self.height:
            self.player_node.set_z(ground_z + self.height)
            self.velocity.z = 0
            self.is_jumping = False

        # Wall collisions (simple implementation)
        # This is a basic "push-back" method. A more robust solution would use
        # multiple raycasts or a collision solid to prevent jittering and getting stuck.
        for dx in [-0.5, 0.5]:
            for dy in [-0.5, 0.5]:
                check_pos = pos + VBase3(dx, dy, -self.height / 2)
                if self.world.get_block(int(check_pos.x), int(check_pos.y), int(check_pos.z)):
                    # Simple push-back. This can be jittery.
                    self.player_node.set_pos(self.last_pos)
                    return
        self.last_pos = self.player_node.get_pos()

    def break_block(self):
        if self.targeted_block:
            self.world.set_block(self.targeted_block[0], self.targeted_block[1], self.targeted_block[2], 0)

    def place_block(self):
        if self.targeted_block:
            self.world.set_block(int(self.place_pos.x), int(self.place_pos.y), int(self.place_pos.z), 1) # Place grass for now

    def get_ground_height(self, x, y, z):
        # Check from player's feet down to find the ground
        for i in range(int(z), -1, -1):
            if self.world.get_block(int(x), int(y), i):
                return i + 1
        return 0
