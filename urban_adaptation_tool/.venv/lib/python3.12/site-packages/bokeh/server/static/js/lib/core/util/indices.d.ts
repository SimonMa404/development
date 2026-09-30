import type { Arrayable } from "../types";
/**
 * Allows to efficiently map back and forth between superset and subset indices.
 * E.g. with superset indices = [0, 1, 2, 3] the subset [1, 3] has subset indices [0, 1].
*/
export declare class SubsetIndexMapper {
    private readonly superset_to_subset;
    private readonly subset_to_superset;
    readonly size: number;
    private size_subset;
    constructor(size: number);
    set_subset(superset_indices: number[]): void;
    get_subset_index(superset_index: number): number;
    has_subset_index(superset_index: number): boolean;
    get_superset_index(subset_index: number): number;
    convert_indices_from_subset(subset_indices: number[]): number[];
    convert_indices_to_subset(superset_indices: number[]): number[];
    subset_index_of(array: Arrayable, value: unknown): number | null;
    private is_superset_index_in_bounds;
    private is_subset_index_in_bounds;
}
//# sourceMappingURL=indices.d.ts.map