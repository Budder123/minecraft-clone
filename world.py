import noise
from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter
from panda3d.core import NodePath, Texture, TextureAttrib, RenderState
from panda3d.core import VBase3

CHUNK_SIZE = 16
CHUNK_HEIGHT = 256

# Block types
GRASS = 1
DIRT = 2
STONE = 3

# Map block IDs to texture names for individual loading
BLOCK_TEXTURE_NAMES = {
    GRASS: "grass",
    DIRT: "dirt",
    STONE: "stone",
}

class World:
    def __init__(self, base):
        self.base = base
        self.chunks = {}

        # --- Robust Texture Loading ---
        self.texture_atlas = None
        self.individual_textures = {}

        # Try to load texture atlas first
        try:
            self.texture_atlas = self.base.loader.loadTexture("textures/texture_atlas.png")
            self.texture_atlas.set_magfilter(Texture.FT_nearest)
            self.texture_atlas.set_minfilter(Texture.FT_nearest)
            print("INFO: Successfully loaded texture atlas.")
        except Exception:
            self.texture_atlas = None
            print("INFO: Texture atlas not found or failed to load. Falling back to individual textures.")
            for block_id, name in BLOCK_TEXTURE_NAMES.items():
                try:
                    tex = self.base.loader.loadTexture(f"textures/{name}.png")
                    tex.set_magfilter(Texture.FT_nearest)
                    tex.set_minfilter(Texture.FT_nearest)
                    self.individual_textures[block_id] = tex
                except Exception:
                    print(f"WARNING: Could not load texture: textures/{name}.png")
                    self.individual_textures[block_id] = None

    def get_block(self, x, y, z):
        if not (0 <= z < CHUNK_HEIGHT):
            return 0
        chunk_x, chunk_y = x // CHUNK_SIZE, y // CHUNK_SIZE
        block_x, block_y = x % CHUNK_SIZE, y % CHUNK_SIZE

        if (chunk_x, chunk_y) not in self.chunks:
            return 0

        return self.chunks[(chunk_x, chunk_y)].blocks[block_x][block_y][z]

    def set_block(self, x, y, z, block_type):
        if not (0 <= z < CHUNK_HEIGHT):
            return

        chunk_x, chunk_y = x // CHUNK_SIZE, y // CHUNK_SIZE
        block_x, block_y = x % CHUNK_SIZE, y % CHUNK_SIZE

        if (chunk_x, chunk_y) in self.chunks:
            chunk = self.chunks[(chunk_x, chunk_y)]
            chunk.blocks[block_x][block_y][z] = block_type
            chunk.generate_mesh()

            # Update neighboring chunks if the block is on a border
            if block_x == 0 and (chunk_x - 1, chunk_y) in self.chunks:
                self.chunks[(chunk_x - 1, chunk_y)].generate_mesh()
            if block_x == CHUNK_SIZE - 1 and (chunk_x + 1, chunk_y) in self.chunks:
                self.chunks[(chunk_x + 1, chunk_y)].generate_mesh()
            if block_y == 0 and (chunk_x, chunk_y - 1) in self.chunks:
                self.chunks[(chunk_x, chunk_y - 1)].generate_mesh()
            if block_y == CHUNK_SIZE - 1 and (chunk_x, chunk_y + 1) in self.chunks:
                self.chunks[(chunk_x, chunk_y + 1)].generate_mesh()

    def generate_chunk(self, chunk_x, chunk_y):
        if (chunk_x, chunk_y) in self.chunks:
            return

        chunk = Chunk(self, chunk_x, chunk_y)
        chunk.generate_terrain()
        chunk.generate_mesh()
        self.chunks[(chunk_x, chunk_y)] = chunk

class Chunk:
    def __init__(self, world, chunk_x, chunk_y):
        self.world = world
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y
        self.blocks = [[[0] * CHUNK_HEIGHT for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
        self.model_node = GeomNode(f"chunk_{chunk_x}_{chunk_y}")
        self.node_path = self.world.base.render.attach_new_node(self.model_node)
        self.node_path.set_pos(chunk_x * CHUNK_SIZE, chunk_y * CHUNK_SIZE, 0)

    def generate_terrain(self):
        for x in range(CHUNK_SIZE):
            for y in range(CHUNK_SIZE):
                world_x = self.chunk_x * CHUNK_SIZE + x
                world_y = self.chunk_y * CHUNK_SIZE + y

                height = int(noise.pnoise2(world_x * 0.01, world_y * 0.01, octaves=3, persistence=0.5, lacunarity=2.0) * 10 + 50)

                for z in range(CHUNK_HEIGHT):
                    if z < height - 3:
                        self.blocks[x][y][z] = STONE
                    elif z < height:
                        self.blocks[x][y][z] = DIRT
                    elif z == height:
                        self.blocks[x][y][z] = GRASS

    def generate_mesh(self):
        self.model_node.remove_all_geoms()

        if self.world.texture_atlas:
            self.generate_mesh_atlas()
        else:
            self.generate_mesh_individual()

    def add_face(self, vertex_writer, texcoord_writer, pos, face_name, uvs):
        # Vertex positions for a 1x1x1 cube
        vertices_map = {
            'top':    (VBase3(0, 0, 1), VBase3(1, 0, 1), VBase3(1, 1, 1), VBase3(0, 1, 1)),
            'bottom': (VBase3(0, 1, 0), VBase3(1, 1, 0), VBase3(1, 0, 0), VBase3(0, 0, 0)),
            'left':   (VBase3(0, 1, 1), VBase3(0, 1, 0), VBase3(0, 0, 0), VBase3(0, 0, 1)),
            'right':  (VBase3(1, 0, 1), VBase3(1, 0, 0), VBase3(1, 1, 0), VBase3(1, 1, 1)),
            'front':  (VBase3(0, 0, 1), VBase3(0, 0, 0), VBase3(1, 0, 0), VBase3(1, 0, 1)),
            'back':   (VBase3(1, 1, 1), VBase3(1, 1, 0), VBase3(0, 1, 0), VBase3(0, 1, 1)),
        }

        verts = vertices_map[face_name]
        for i in range(4):
            vertex_writer.add_data3(pos + verts[i])
            texcoord_writer.add_data2(uvs[i])
        return 4 # 4 vertices added

    def generate_mesh_atlas(self):
        vdata = GeomVertexData('chunk_data', GeomVertexFormat.get_v3t2(), Geom.UH_static)
        vertex = GeomVertexWriter(vdata, 'vertex')
        texcoord = GeomVertexWriter(vdata, 'texcoord')
        tris = GeomTriangles(Geom.UH_static)

        # UV mapping for a 3x1 texture atlas
        uv_map = {
            GRASS: ((0, 1), (1/3, 1), (1/3, 0), (0, 0)),
            DIRT:  ((1/3, 1), (2/3, 1), (2/3, 0), (1/3, 0)),
            STONE: ((2/3, 1), (1, 1), (1, 0), (2/3, 0)),
        }
        # Flip UVs vertically to match Panda's convention
        uv_map_flipped = {k: [(u, 1-v) for u, v in val] for k, val in uv_map.items()}

        vertex_count = 0
        for x, y, z, block_type, neighbors in self.iterate_blocks():
            pos = VBase3(x, y, z)
            uvs = uv_map_flipped[block_type]

            if not neighbors[0]: # Top
                v_count = self.add_face(vertex, texcoord, pos, 'top', uvs)
                tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                vertex_count += v_count
            # ... repeat for all 6 faces ...
            if not neighbors[1]: # Bottom
                v_count = self.add_face(vertex, texcoord, pos, 'bottom', uvs)
                tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                vertex_count += v_count
            if not neighbors[2]: # Left
                v_count = self.add_face(vertex, texcoord, pos, 'left', uvs)
                tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                vertex_count += v_count
            if not neighbors[3]: # Right
                v_count = self.add_face(vertex, texcoord, pos, 'right', uvs)
                tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                vertex_count += v_count
            if not neighbors[4]: # Front
                v_count = self.add_face(vertex, texcoord, pos, 'front', uvs)
                tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                vertex_count += v_count
            if not neighbors[5]: # Back
                v_count = self.add_face(vertex, texcoord, pos, 'back', uvs)
                tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                vertex_count += v_count

        geom = Geom(vdata)
        geom.add_primitive(tris)
        self.model_node.add_geom(geom)
        self.node_path.set_texture(self.world.texture_atlas)

    def generate_mesh_individual(self):
        geoms = {}
        uvs = ((0, 0), (1, 0), (1, 1), (0, 1)) # Standard UVs for a single texture

        for x, y, z, block_type, neighbors in self.iterate_blocks():
            if block_type not in geoms:
                vdata = GeomVertexData('chunk_data', GeomVertexFormat.get_v3t2(), Geom.UH_static)
                tris = GeomTriangles(Geom.UH_static)
                geoms[block_type] = {
                    'vdata': vdata,
                    'vertex': GeomVertexWriter(vdata, 'vertex'),
                    'texcoord': GeomVertexWriter(vdata, 'texcoord'),
                    'tris': tris,
                    'vertex_count': 0
                }

            geom_data = geoms[block_type]
            pos = VBase3(x, y, z)

            face_checks = [
                (not neighbors[0], 'top'), (not neighbors[1], 'bottom'),
                (not neighbors[2], 'left'), (not neighbors[3], 'right'),
                (not neighbors[4], 'front'), (not neighbors[5], 'back')
            ]

            for should_add, face_name in face_checks:
                if should_add:
                    v_count = self.add_face(geom_data['vertex'], geom_data['texcoord'], pos, face_name, uvs)
                    vc = geom_data['vertex_count']
                    geom_data['tris'].add_vertices(vc, vc + 1, vc + 2)
                    geom_data['tris'].add_vertices(vc + 2, vc + 3, vc)
                    geom_data['vertex_count'] += v_count

        for block_type, geom_data in geoms.items():
            geom = Geom(geom_data['vdata'])
            geom.add_primitive(geom_data['tris'])

            state = RenderState.make_empty()
            texture = self.world.individual_textures.get(block_type)
            if texture:
                state = state.add_attrib(TextureAttrib.make(texture))

            self.model_node.add_geom(geom, state)

    def is_block_solid(self, x, y, z):
        if not (0 <= x < CHUNK_SIZE and 0 <= y < CHUNK_SIZE and 0 <= z < CHUNK_HEIGHT):
            world_x = self.chunk_x * CHUNK_SIZE + x
            world_y = self.chunk_y * CHUNK_SIZE + y
            return self.world.get_block(world_x, world_y, z) > 0
        return self.blocks[x][y][z] > 0

    def iterate_blocks(self):
        """Yields position, block type, and neighbor solidity for each non-air block."""
        for x in range(CHUNK_SIZE):
            for y in range(CHUNK_SIZE):
                for z in range(CHUNK_HEIGHT):
                    block_type = self.blocks[x][y][z]
                    if not block_type:
                        continue

                    neighbors = (
                        self.is_block_solid(x, y, z + 1), # Top
                        self.is_block_solid(x, y, z - 1), # Bottom
                        self.is_block_solid(x - 1, y, z), # Left
                        self.is_block_solid(x + 1, y, z), # Right
                        self.is_block_solid(x, y - 1, z), # Front
                        self.is_block_solid(x, y + 1, z)  # Back
                    )

                    if not all(neighbors):
                        yield x, y, z, block_type, neighbors
