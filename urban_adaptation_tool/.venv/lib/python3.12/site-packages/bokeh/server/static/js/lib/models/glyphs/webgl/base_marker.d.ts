import type { Vec4 } from "regl";
import type { Transform } from "./base";
import { BaseGLGlyph } from "./base";
import { Float32Buffer, NormalizedUint8Buffer, Uint8Buffer } from "./buffer";
import type { LineProps, FillProps, HatchProps, GLMarkerType } from "./types";
import type * as visuals from "../../../core/visuals";
export type MarkerVisuals = {
    readonly line: visuals.LineVector;
    readonly fill: visuals.FillVector;
    readonly hatch: visuals.HatchVector;
};
export declare abstract class BaseMarkerGL extends BaseGLGlyph {
    private readonly _antialias;
    protected readonly _centers: Float32Buffer;
    protected readonly _widths: Float32Buffer;
    protected readonly _heights: Float32Buffer;
    protected readonly _angles: Float32Buffer;
    protected readonly _auxs: Float32Buffer;
    protected _border_radius: Vec4;
    protected _border_radius_nonzero: boolean;
    protected readonly _show: Uint8Buffer;
    protected _show_all: boolean;
    protected readonly _linewidths: Float32Buffer;
    protected readonly _line_caps: Uint8Buffer;
    protected readonly _line_joins: Uint8Buffer;
    protected readonly _line_rgba: NormalizedUint8Buffer;
    protected readonly _fill_rgba: NormalizedUint8Buffer;
    protected _have_hatch: boolean;
    protected readonly _hatch_patterns: Uint8Buffer;
    protected readonly _hatch_scales: Float32Buffer;
    protected readonly _hatch_weights: Float32Buffer;
    protected readonly _hatch_rgba: NormalizedUint8Buffer;
    protected static readonly missing_point = -10000;
    /**
     * Selects appropriate geometry buffers for rendering a marker glyph.
     *
     * This method implements smart buffer selection to support property overrides in derived
     * glyphs (hover_glyph, selection_glyph, muted_glyph). For each geometry property, it
     * checks if the derived glyph has populated its own buffer; if so, that buffer is used,
     * otherwise it falls back to the main glyph's buffer.
     *
     * This pattern enables zero-overhead overrides: derived glyphs that don't override
     * properties simply reuse main glyph buffers, while overrides are handled via lazy
     * buffer creation detected by length checks.
     *
     * @param derived_gl - The glyph being rendered (may be main or derived glyph)
     * @param main_gl_glyph - The main glyph (used as fallback for unpopulated buffers)
     * @returns Object with buffer references for width, height, angle, aux, and border_radius
     *
     * Note: border_radius always uses main glyph buffer (overrides not supported)
     */
    marker_props(derived_gl: BaseMarkerGL, main_gl_glyph: BaseMarkerGL): {
        width: Float32Buffer;
        height: Float32Buffer;
        angle: Float32Buffer;
        aux: Float32Buffer;
        border_radius: Vec4;
    };
    get line_props(): LineProps;
    get fill_props(): FillProps;
    get hatch_props(): HatchProps;
    protected _draw_one_marker_type(marker_type: GLMarkerType, transform: Transform, main_gl_glyph: BaseMarkerGL): void;
    private _did_set_once;
    set_data(): void;
    protected abstract _set_data(): void;
    protected _set_once(): void;
    protected abstract _get_visuals(): MarkerVisuals;
    protected _set_visuals(): void;
}
//# sourceMappingURL=base_marker.d.ts.map