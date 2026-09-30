import { Texture } from "./texture";
import type * as p from "../../core/properties";
import type { Color } from "../../core/types";
import type { PatternSource } from "../../core/visuals/patterns";
import { ImageLoader } from "../../core/util/image";
export declare namespace ImageURLTexture {
    type Attrs = p.AttrsOf<Props>;
    type Props = Texture.Props & {
        url: p.Property<string>;
    } & Internal;
    type Internal = {
        _loader: p.Property<ImageLoader>;
    };
}
export interface ImageURLTexture extends ImageURLTexture.Attrs {
}
export declare class ImageURLTexture extends Texture {
    properties: ImageURLTexture.Props;
    constructor(attrs?: Partial<ImageURLTexture.Attrs>);
    get_pattern(_color: Color, _scale: number, _weight: number): PatternSource | Promise<PatternSource>;
}
//# sourceMappingURL=image_url_texture.d.ts.map