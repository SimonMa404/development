import type { Tile } from "./tile_source";
import type { Extent, Bounds } from "./tile_utils";
import { TileSource } from "./tile_source";
import { Renderer, RendererView } from "../renderers/renderer";
import { HTML } from "../dom/html";
import type * as p from "../../core/properties";
import type { Image } from "../../core/util/image";
import type { Context2d } from "../../core/util/canvas";
export type TileData = Tile & ({
    img: Image;
    loaded: true;
} | {
    img: undefined;
    loaded: false;
}) & {
    quadkey: string;
    cache_key: string;
    bounds: Bounds;
    /** Whether the image request settled, either by loading or by failing. */
    finished: boolean;
    /** Number of image requests issued for this tile. */
    attempts: number;
};
type Size = {
    width: number;
    height: number;
};
export declare class TileRendererView extends RendererView {
    model: TileRenderer;
    protected extent: Extent;
    protected map_initialized: boolean;
    /** Frame size, in CSS pixels, the extent was last adjusted to. */
    protected _last_size: Size | null;
    /** Zoom level the last update drew, if any. */
    protected _last_level: number | null;
    /** Whether at least one update completed, i.e. whether tiles are known. */
    protected _updated: boolean;
    /** Tiles the last update asked for, not requested yet. */
    protected _to_fetch: [number, number, number, Bounds][];
    /** Keys of tiles with an image request in flight. */
    protected _loading: Set<string>;
    /**
     * Tiles with an image request in flight, held outside the bounded cache so
     * that they can't be evicted before they arrive, which would lose track of
     * the request and of how many attempts were already made.
     */
    protected _pending: Map<string, TileData>;
    /** Keys of the tiles the current extent needs, which are never evicted. */
    protected _current: Set<string>;
    protected _fetch_timer: number | null;
    protected _prefetch_timer: number | null;
    connect_signals(): void;
    remove(): void;
    protected _clear_timers(): void;
    force_finished(): void;
    has_finished(): boolean;
    get attribution(): HTML | string | null;
    private get x_range();
    private get y_range();
    get_extent(): Extent;
    /**
     * Assigns an extent's interval to a range, preserving its orientation and
     * optionally making it the range's reset state.
     */
    private _set_range;
    /**
     * The size of the frame in tile image pixels, which is the unit zoom levels
     * are expressed in. The display may have more device pixels than CSS pixels,
     * and a source may serve more image pixels than tile pixels ("@2x" tiles).
     */
    protected _tile_pixel_size(): Size;
    protected _init_map({ width, height }: Size): void;
    /**
     * Adjusts the ranges so that both axes resolve to the same number of meters
     * per pixel, within the range of zoom levels the source provides. Without
     * this, anything that scales the axes independently (a box zoom, a single
     * dimension wheel zoom, an auto-ranged range) leaves the tiles distorted.
     */
    protected _enforce_extent({ width, height }: Size): void;
    protected _paint(ctx: Context2d): void;
    protected _update(ctx: Context2d): void;
    protected _get_tile(key: string): TileData | undefined;
    protected _is_loaded(key: string): boolean;
    /**
     * Whether a tile has to be requested. Tiles that failed are retried, but only
     * a bounded number of times, so that a broken source isn't requested forever.
     */
    protected _needs_load(tile: TileData | undefined): boolean;
    protected _fetch_tiles(): void;
    protected _schedule_prefetch(): void;
    protected _prefetch_tiles(): void;
    protected _create_tile(x: number, y: number, z: number, bounds: Bounds, cache_only?: boolean): void;
    protected _render_tiles(ctx: Context2d, tile_keys: Iterable<string>): void;
    protected _draw_tile(ctx: Context2d, tile_key: string): void;
    protected _set_rect(ctx: Context2d): void;
}
export declare namespace TileRenderer {
    type Attrs = p.AttrsOf<Props>;
    type Props = Renderer.Props & {
        alpha: p.Property<number>;
        smoothing: p.Property<boolean>;
        tile_source: p.Property<TileSource>;
        render_parents: p.Property<boolean>;
    };
}
export interface TileRenderer extends TileRenderer.Attrs {
}
export declare class TileRenderer extends Renderer {
    properties: TileRenderer.Props;
    __view_type__: TileRendererView;
    constructor(attrs?: Partial<TileRenderer.Attrs>);
}
export {};
//# sourceMappingURL=tile_renderer.d.ts.map