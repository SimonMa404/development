import type { PlainObject } from "../types";
export declare const equals: unique symbol;
export interface Equatable {
    [equals](that: this, cmp: Comparator): boolean;
}
export declare const wildcard: any;
export declare class EqNotImplemented extends Error {
}
export type ComparatorOptions = {
    /**
     * Compare the structure of objects even if an identity check would be more
     * robust (default: false)
     */
    structural?: boolean;
    /**
     * Don't throw any exceptions if values don't support equality, but simply
     * return they aren't equal (default: false)
     */
    no_fail?: boolean;
};
export declare class Comparator {
    private readonly a_stack;
    private readonly b_stack;
    readonly structural: boolean;
    readonly no_fail: boolean;
    constructor(options?: ComparatorOptions);
    eq(a: any, b: any): boolean;
    numbers(a: number, b: number): boolean;
    arrays(a: ArrayLike<unknown>, b: ArrayLike<unknown>): boolean;
    array_buffers(a: ArrayBufferLike, b: ArrayBufferLike): boolean;
    iterables(a: Iterable<unknown>, b: Iterable<unknown>): boolean;
    maps(a: Map<unknown, unknown>, b: Map<unknown, unknown>): boolean;
    sets(a: Set<unknown>, b: Set<unknown>): boolean;
    objects(a: PlainObject, b: PlainObject): boolean;
    nodes(a: Node, b: Node): boolean;
}
export declare class SimilarComparator extends Comparator {
    readonly tolerance: number;
    constructor(tolerance?: number);
    numbers(a: number, b: number): boolean;
}
export declare function is_equal(a: unknown, b: unknown): boolean;
export declare function is_structurally_equal(a: unknown, b: unknown): boolean;
export declare function is_similar(a: unknown, b: unknown, tolerance?: number): boolean;
//# sourceMappingURL=eq.d.ts.map