import noise
from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter
from panda3d.core import NodePath, Texture, TextureStage
from panda3d.core import VBase3

CHUNK_SIZE = 16
CHUNK_HEIGHT = 256

# Block types
GRASS = 1
DIRT = 2
STONE = 3

class World:
    def __init__(self, base):
        self.base = base
        self.chunks = {}
        self.texture = self.base.loader.loadTexture("textures/texture_atlas.png") # Placeholder, will need to create a texture atlas
        if not self.texture:
            # Fallback to separate textures if atlas is missing
            self.textures = {
                GRASS: self.base.loader.loadTexture("textures/grass.png"),
                DIRT: self.base.loader.loadTexture("textures/dirt.png"),
                STONE: self.base.loader.loadTexture("textures/stone.png"),
            }
        self.texture.set_magfilter(Texture.FT_nearest)
        self.texture.set_minfilter(Texture.FT_nearest)


    def get_block(self, x, y, z):
        chunk_x, chunk_y = x // CHUNK_SIZE, y // CHUNK_SIZE
        block_x, block_y = x % CHUNK_SIZE, y % CHUNK_SIZE

        if (chunk_x, chunk_y) not in self.chunks:
            return None # Or generate the chunk here

        return self.chunks[(chunk_x, chunk_y)].blocks[block_x][block_y][z]

    def generate_chunk(self, chunk_x, chunk_y):
        if (chunk_x, chunk_y) in self.chunks:
            return

        chunk = Chunk(self, chunk_x, chunk_y)
        chunk.generate_terrain()
        chunk.generate_mesh()
        self.chunks[(chunk_x, chunk_y)] = chunk

    def set_block(self, x, y, z, block_type):
        chunk_x, chunk_y = x // CHUNK_SIZE, y // CHUNK_SIZE
        block_x, block_y = x % CHUNK_SIZE, y % CHUNK_SIZE

        if (chunk_x, chunk_y) in self.chunks:
            chunk = self.chunks[(chunk_x, chunk_y)]
            chunk.blocks[block_x][block_y][z] = block_type
            chunk.generate_mesh()

            # Check and update neighboring chunks if the block is on a border
            if block_x == 0 and (chunk_x - 1, chunk_y) in self.chunks:
                self.chunks[(chunk_x - 1, chunk_y)].generate_mesh()
            if block_x == CHUNK_SIZE - 1 and (chunk_x + 1, chunk_y) in self.chunks:
                self.chunks[(chunk_x + 1, chunk_y)].generate_mesh()
            if block_y == 0 and (chunk_x, chunk_y - 1) in self.chunks:
                self.chunks[(chunk_x, chunk_y - 1)].generate_mesh()
            if block_y == CHUNK_SIZE - 1 and (chunk_x, chunk_y + 1) in self.chunks:
                self.chunks[(chunk_x, chunk_y + 1)].generate_mesh()


class Chunk:
    def __init__(self, world, chunk_x, chunk_y):
        self.world = world
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y
        self.blocks = [[[0] * CHUNK_HEIGHT for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
        self.model_node = GeomNode(f"chunk_{chunk_x}_{chunk_y}")
        self.node_path = self.world.base.render.attach_new_node(self.model_node)
        self.node_path.set_pos(chunk_x * CHUNK_SIZE, chunk_y * CHUNK_SIZE, 0)
        self.node_path.set_texture(self.world.texture)

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

        vdata = GeomVertexData('chunk_data', GeomVertexFormat.get_v3t2(), Geom.UH_static)
        vdata.set_num_rows(CHUNK_SIZE * CHUNK_SIZE * CHUNK_HEIGHT * 24) # Pre-allocate memory

        vertex_writer = GeomVertexWriter(vdata, 'vertex')
        texcoord_writer = GeomVertexWriter(vdata, 'texcoord')

        tris = GeomTriangles(Geom.UH_static)

        vertex_count = 0

        for x in range(CHUNK_SIZE):
            for y in range(CHUNK_SIZE):
                for z in range(CHUNK_HEIGHT):
                    block_type = self.blocks[x][y][z]
                    if not block_type:
                        continue

                    # Check neighbors
                    # top, bottom, left, right, front, back
                    neighbors = [
                        self.is_block_solid(x, y, z + 1),
                        self.is_block_solid(x, y, z - 1),
                        self.is_block_solid(x - 1, y, z),
                        self.is_block_solid(x + 1, y, z),
                        self.is_block_solid(x, y - 1, z),
                        self.is_block_solid(x, y + 1, z)
                    ]

                    if not all(neighbors):
                        # Position of the block in the chunk
                        pos = VBase3(x, y, z)

                        # Add faces
                        # Top
                        if not neighbors[0]:
                            v_count = self.add_face(vertex_writer, texcoord_writer, pos, 'top', block_type)
                            tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                            tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                            vertex_count += v_count

                        # Bottom
                        if not neighbors[1]:
                            v_count = self.add_face(vertex_writer, texcoord_writer, pos, 'bottom', block_type)
                            tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                            tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                            vertex_count += v_count

                        # Left
                        if not neighbors[2]:
                            v_count = self.add_face(vertex_writer, texcoord_writer, pos, 'left', block_type)
                            tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                            tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                            vertex_count += v_count

                        # Right
                        if not neighbors[3]:
                            v_count = self.add_face(vertex_writer, texcoord_writer, pos, 'right', block_type)
                            tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                            tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                            vertex_count += v_count

                        # Front
                        if not neighbors[4]:
                            v_count = self.add_face(vertex_writer, texcoord_writer, pos, 'front', block_type)
                            tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                            tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                            vertex_count += v_count

                        # Back
                        if not neighbors[5]:
                            v_count = self.add_face(vertex_writer, texcoord_writer, pos, 'back', block_type)
                            tris.add_vertices(vertex_count, vertex_count + 1, vertex_count + 2)
                            tris.add_vertices(vertex_count + 2, vertex_count + 3, vertex_count)
                            vertex_count += v_count

        geom = Geom(vdata)
        geom.add_primitive(tris)
        self.model_node.add_geom(geom)

    def is_block_solid(self, x, y, z):
        if not (0 <= x < CHUNK_SIZE and 0 <= y < CHUNK_SIZE and 0 <= z < CHUNK_HEIGHT):
            # Query world for neighboring chunks
            world_x = self.chunk_x * CHUNK_SIZE + x
            world_y = self.chunk_y * CHUNK_SIZE + y
            block = self.world.get_block(world_x, world_y, z)
            return block is not None and block > 0

        return self.blocks[x][y][z] > 0

    def add_face(self, vertex_writer, texcoord_writer, pos, face, block_type):
        # UV mapping for a simple texture atlas.
        # This assumes a 3x1 atlas where:
        # (0,0) is GRASS, (1,0) is DIRT, (2,0) is STONE
        uv_pos = {
            GRASS: (0, 0),
            DIRT: (1, 0),
            STONE: (2, 0),
        }
        u, v = uv_pos[block_type]
        uv_size = 1/3 # Assuming 3 textures in a row

        vertices = [
            # Top
            (pos + VBase3(0, 0, 1), pos + VBase3(1, 0, 1), pos + VBase3(1, 1, 1), pos + VBase3(0, 1, 1)),
            # Bottom
            (pos + VBase3(0, 1, 0), pos + VBase3(1, 1, 0), pos + VBase3(1, 0, 0), pos + VBase3(0, 0, 0)),
            # Left
            (pos + VBase3(0, 1, 1), pos + VBase3(0, 1, 0), pos + VBase3(0, 0, 0), pos + VBase3(0, 0, 1)),
            # Right
            (pos + VBase3(1, 0, 1), pos + VBase3(1, 0, 0), pos + VBase3(1, 1, 0), pos + VBase3(1, 1, 1)),
            # Front
            (pos + VBase3(0, 0, 1), pos + VBase3(0, 0, 0), pos + VBase3(1, 0, 0), pos + VBase3(1, 0, 1)),
            # Back
            (pos + VBase3(1, 1, 1), pos + VBase3(1, 1, 0), pos + VBase3(0, 1, 0), pos + VBase3(0, 1, 1))
        ]

        uvs = [
            ((u * uv_size, v * uv_size + uv_size), (u * uv_size + uv_size, v * uv_size + uv_size), (u * uv_size + uv_size, v * uv_size), (u * uv_size, v * uv_size)),
        ]

        face_map = {'top': 0, 'bottom': 1, 'left': 2, 'right': 3, 'front': 4, 'back': 5}

        for i in range(4):
            vertex_writer.add_data3(vertices[face_map[face]][i])
            # This is a simplified UV mapping. It should be improved for a real texture atlas
            texcoord_writer.add_data2(uvs[0][i])

        return 4
