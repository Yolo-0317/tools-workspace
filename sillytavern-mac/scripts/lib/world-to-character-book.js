/**
 * ST 世界书 entries（Map）→ chara_card_v2 character_book（Array）
 * NativeTavern / V2 规范要求 entries 为 List，不能是 {"0": {...}}。
 */
export function worldToCharacterBook(world, { name, description, scan_depth = 2, token_budget = 768 } = {}) {
    const entriesMap = world?.entries ?? {};
    const entries = [];

    for (const index of Object.keys(entriesMap).sort((a, b) => Number(a) - Number(b))) {
        const e = entriesMap[index];
        entries.push({
            id: e.uid ?? Number(index),
            keys: e.key ?? [],
            secondary_keys: e.keysecondary ?? [],
            comment: e.comment ?? '',
            content: e.content ?? '',
            constant: !!e.constant,
            selective: !!e.selective,
            insertion_order: e.order ?? 100,
            enabled: !e.disable,
            use_regex: true,
            case_sensitive: e.caseSensitive ?? false,
            name: e.comment ?? '',
            priority: e.order ?? 100,
            position: (e.position === 0 || e.position === 'before_char') ? 'before_char' : 'after_char',
            extensions: {
                ...(e.extensions ?? {}),
                position: e.position ?? 0,
                exclude_recursion: e.excludeRecursion ?? false,
                prevent_recursion: e.preventRecursion ?? false,
                display_index: e.displayIndex ?? Number(index),
                probability: e.probability ?? 100,
                useProbability: e.useProbability ?? true,
                depth: e.depth ?? 4,
                group: e.group ?? '',
                scan_depth: e.scanDepth ?? null,
                match_whole_words: e.matchWholeWords ?? null,
                case_sensitive: e.caseSensitive ?? null,
            },
        });
    }

    return {
        name,
        description,
        scan_depth,
        token_budget,
        recursive_scanning: false,
        extensions: {},
        entries,
    };
}
