import { TileSource } from "./tile_source";
import type * as p from "../../core/properties";
import type { Extent, Bounds } from "./tile_utils";
export declare namespace MercatorTileSource {
    type Attrs = p.AttrsOf<Props>;
    type Props = TileSource.Props & {
        snap_to_zoom: p.Property<boolean>;
        wrap_around: p.Property<boolean>;
    } & Internal;
    type Internal = {
        _resolutions: p.Property<number[]>;
    };
}
export interface MercatorTileSource extends MercatorTileSource.Attrs {
}
export declare class MercatorTileSource extends TileSource {
    properties: MercatorTileSource.Props;
    constructor(attrs?: Partial<MercatorTileSource.Attrs>);
    /**
     * The coarsest zoom level provided by this source.
     */
    get min_level(): number;
    /**
     * The finest zoom level provided by this source.
     */
    get max_level(): number;
    protected _computed_initial_resolution(): number;
    is_valid_tile(x: number, y: number, z: number): boolean;
    get_resolution(level: number): number;
    get_resolution_by_extent(extent: Extent, height: number, width: number): [number, number];
    /**
     * The resolution needed to fit `extent` into `width` x `height` pixels.
     */
    protected _required_resolution(extent: Extent, height: number, width: number): number;
    /**
     * The finest level whose tiles still cover `extent`, i.e. the extent is
     * never cropped, at the cost of drawing tiles magnified up to 2x.
     */
    get_level_by_extent(extent: Extent, height: number, width: number): number;
    /**
     * The level whose resolution is closest to the one `extent` requires, which
     * keeps tiles within a factor of sqrt(2) of their native size.
     */
    get_closest_level_by_extent(extent: Extent, height: number, width: number): number;
    /**
     * `extent` grown or shrunk around its center to `resolution` in both axes.
     */
    protected _extent_at_resolution(extent: Extent, height: number, width: number, resolution: number): Extent;
    snap_to_zoom_level(extent: Extent, height: number, width: number, level: number): Extent;
    /**
     * `extent` adjusted so that both axes resolve to the same number of meters
     * per pixel, by growing the axis that has room to spare. Tiles are square, so
     * an extent that scales the axes independently (as a box zoom, a single
     * dimension wheel zoom, or an auto-ranged range does) draws them distorted.
     */
    constrain_extent(extent: Extent, height: number, width: number): Extent;
    rescale(extent: Extent, height: number, width: number, last_height: number, last_width: number): Extent;
    tms_to_wmts(x: number, y: number, z: number): [number, number, number];
    wmts_to_tms(x: number, y: number, z: number): [number, number, number];
    pixels_to_meters(px: number, py: number, level: number): [number, number];
    meters_to_pixels(mx: number, my: number, level: number): [number, number];
    pixels_to_tile(px: number, py: number): [number, number];
    meters_to_tile(mx: number, my: number, level: number): [number, number];
    get_tile_meter_bounds(tx: number, ty: number, level: number): Bounds;
    get_tile_geographic_bounds(tx: number, ty: number, level: number): Bounds;
    get_tiles_by_extent(extent: Extent, level: number, tile_border?: number): [number, number, number, Bounds][];
    quadkey_to_tile_xyz(quadKey: string): [number, number, number];
    tile_xyz_to_quadkey(x: number, y: number, z: number): string;
    children_by_tile_xyz(x: number, y: number, z: number): [number, number, number, Bounds][];
    get_closest_parent_by_tile_xyz(x: number, y: number, z: number): [number, number, number] | null;
    normalize_xyz(x: number, y: number, z: number): [number, number, number];
    denormalize_xyz(x: number, y: number, z: number, world_x: number): [number, number, number];
    calculate_world_x_by_tile_xyz(x: number, _y: number, z: number): number;
}
//# sourceMappingURL=mercator_tile_source.d.ts.map