import type { HitTestResult } from "../../core/hittest";
import * as p from "../../core/properties";
import * as visuals from "../../core/visuals";
import * as uniforms from "../../core/uniforms";
import type * as geometry from "../../core/geometry";
import type { Context2d } from "../../core/util/canvas";
import { DOMComponentView } from "../../core/dom_view";
import { Model } from "../../model";
import type { Anchor, WindowAxis } from "../../core/enums";
import type { ViewStorage, ChildView } from "../../core/build_views";
import type { Arrayable, Rect, FloatArray } from "../../core/types";
import { ScreenArray, Indices } from "../../core/types";
import { RaggedArray } from "../../core/util/ragged_array";
import { SpatialIndex } from "../../core/util/spatial";
import { BBox } from "../../core/util/bbox";
import type { Scale } from "../scales/scale";
import { Selection } from "../selections/selection";
import type { GlyphRendererView } from "../renderers/glyph_renderer";
import type { ColumnarDataSource } from "../sources/columnar_data_source";
import { Decoration } from "../graphics/decoration";
import type { BaseGLGlyph } from "./webgl/base";
export declare const inherit: unique symbol;
type ValueLike = number | uniforms.Uniform<unknown> | Arrayable<unknown> | RaggedArray<any>;
export interface GlyphView extends Glyph.Data {
}
export declare abstract class GlyphView extends DOMComponentView {
    model: Glyph;
    visuals: Glyph.Visuals;
    readonly parent: GlyphRendererView;
    get renderer(): GlyphRendererView;
    load_glglyph?(): Promise<typeof BaseGLGlyph>;
    has_webgl(): this is {
        glglyph: BaseGLGlyph;
    };
    private _can_use_webgl;
    protected _compute_can_use_webgl(): boolean;
    private _index;
    private _data_size;
    protected _nohit_warned: Set<geometry.Geometry["type"]>;
    get index(): SpatialIndex;
    get data_size(): number;
    initialize(): void;
    readonly decorations: ViewStorage<Decoration>;
    children_views(): ChildView[];
    lazy_initialize(): Promise<void>;
    request_paint(): void;
    get canvas(): import("../canvas/canvas").CanvasView;
    paint(ctx: Context2d, indices: number[], data?: Partial<Glyph.Data>): void;
    protected abstract _paint(ctx: Context2d, indices: number[], data?: Glyph.Data): void;
    has_finished(): boolean;
    notify_finished(): void;
    protected _bounds(bounds: Rect): Rect;
    bounds(window_axis?: WindowAxis): Rect;
    log_bounds(): Rect;
    get_anchor_point(anchor: Anchor, i: number, [sx, sy]: [number, number]): {
        x: number;
        y: number;
    } | null;
    abstract scenterxy(i: number, sx: number, sy: number): [number, number];
    sdist(scale: Scale, pts: Arrayable<number>, spans: p.Uniform<number>, pts_location?: "center" | "edge", dilate?: boolean): ScreenArray;
    draw_legend_for_index(_ctx: Context2d, _bbox: Rect, _index: number): void;
    protected _hit_point?(geometry: geometry.PointGeometry): Selection;
    protected _hit_span?(geometry: geometry.SpanGeometry): Selection;
    protected _hit_rect?(geometry: geometry.RectGeometry): Selection;
    protected _hit_poly?(geometry: geometry.PolyGeometry): Selection;
    hit_test(geometry: geometry.Geometry): HitTestResult;
    protected _hit_rect_against_index(geometry: geometry.RectGeometry): Selection;
    protected _project_xy<Data>(x: keyof Data, xs: Arrayable<number>, y: keyof Data, ys: Arrayable<number>): void;
    protected _project_data(): void;
    private _iter_visuals;
    protected _base: this | null;
    get base(): this | null;
    set_base<T extends this>(base: T): void;
    protected _define_or_inherit_attr<Data>(attr: keyof Data, fn: () => typeof inherit | ValueLike): void;
    protected _define_attr<Data>(attr: keyof Data, value: ValueLike): void;
    protected _inherit_attr<Data>(attr: keyof Data): void;
    protected _inherit_from<Data>(attr: keyof Data, base: this): void;
    protected _define_inherited<Data>(attr: keyof Data, value: boolean): void;
    /**
     * Determine if this view can inherit a property value from the base glyph.
     *
     * This enables selection/hover/muted glyphs to inherit properties from the base
     * glyph when not explicitly overridden, which is critical when a derived glyph
     * only overrides some properties (e.g., radius) but should inherit others
     * (e.g., start_angle, end_angle).
     *
     * Inheritance occurs when either:
     * 1. The derived property value equals the base value (original behavior), OR
     * 2. The derived property value equals its default (new behavior)
     *
     * Example (case 2):
     *   Base glyph: start_angle: {value: 0}
     *   Selection glyph: (unspecified) → gets default {field: "start_angle"}
     *   Without inheritance: would try to read missing field → rendering fails
     *   With inheritance: inherits {value: 0} from base → renders correctly ✓
     *
     * @param prop - The property to check for inheritance
     * @param base - The base glyph view to potentially inherit from
     * @returns true if the property should be inherited from base
     */
    protected _can_inherit_from<T>(prop: p.Property<T>, base: this | null): boolean;
    protected _is_inherited<T>(prop: p.Property<T> | string): boolean;
    set_visuals(source: ColumnarDataSource, indices: Indices): void;
    protected _transform_array<T>(prop: p.BaseCoordinateSpec<T>, array: Arrayable<unknown>): Arrayable<unknown> | RaggedArray<FloatArray>;
    set_data(source: ColumnarDataSource, indices: Indices, indices_to_update?: number[]): Promise<void>;
    protected _set_data(_indices: number[] | null): void;
    protected _set_lazy_data(_indices: number[] | null): Promise<void>;
    /**
     * Any data transformations that require visuals.
     */
    after_visuals(): void;
    after_lazy_visuals(): Promise<void>;
    protected get _index_size(): number;
    protected abstract _index_data(index: SpatialIndex): void;
    index_data(): void;
    mask_data(): Indices;
    protected _mask_data?(): Indices;
    map_data(): void;
    protected _map_data(): void;
    get bbox(): BBox | undefined;
}
export declare namespace Glyph {
    type Attrs = p.AttrsOf<Props>;
    type Props = Model.Props & {
        decorations: p.Property<Decoration[]>;
    };
    type Visuals = visuals.Visuals;
    type Data = p.GlyphDataOf<Props>;
}
export interface Glyph extends Glyph.Attrs {
}
export declare abstract class Glyph extends Model {
    properties: Glyph.Props;
    __view_type__: GlyphView;
    constructor(attrs?: Partial<Glyph.Attrs>);
}
export {};
//# sourceMappingURL=glyph.d.ts.map