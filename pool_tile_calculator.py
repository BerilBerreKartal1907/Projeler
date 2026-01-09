import math

def calculate_tile_size(pool_width: int, pool_length: int, pool_depth: int) -> tuple[int, int]:
    """
    Calculates the maximum square tile size that can be used
    to cover all pool surfaces without cutting.
    """
    gcd_base = math.gcd(pool_width, pool_length)
    tile_size = math.gcd(gcd_base, pool_depth)
    return tile_size, tile_size


def calculate_tile_count(pool_dimensions: tuple[int, int, int],
                         tile_dimensions: tuple[int, int]) -> int:
    """
    Calculates the total number of tiles required to cover
    the pool floor, ceiling, and side surfaces.
    """
    pool_width, pool_length, pool_depth = pool_dimensions
    tile_width, tile_length = tile_dimensions

    floor_and_ceiling_area = 2 * (pool_width * pool_length)
    side_area_width = 2 * (pool_width * pool_depth)
    side_area_length = 2 * (pool_length * pool_depth)

    total_surface_area = floor_and_ceiling_area + side_area_width + side_area_length
    tile_area = tile_width * tile_length

    return total_surface_area // tile_area


# Example usage
pool_width = 10
pool_length = 15
pool_depth = 5

tile_dimensions = calculate_tile_size(pool_width, pool_length, pool_depth)
print(f"Tile size: {tile_dimensions}")

pool_dimensions = (pool_width, pool_length, pool_depth)
total_tiles = calculate_tile_count(pool_dimensions, tile_dimensions)
print(f"Total number of tiles required: {total_tiles}")
