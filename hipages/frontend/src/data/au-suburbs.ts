// Australian suburbs & postcodes — static dataset
// Source: Australian locations directory (all states & territories)
// Searched instantly client-side — no API call needed

export interface AustralianSuburb {
    suburb: string;
    postcode: string;
    state: string;
}

export const AU_SUBURBS: AustralianSuburb[] = [
    // ── Australian Capital Territory ──────────────────────────────────────────
    { suburb: "Braddon", postcode: "2601", state: "ACT" },
    { suburb: "Canberra", postcode: "2601", state: "ACT" },
    { suburb: "Canberra Airport", postcode: "2609", state: "ACT" },

    // ── New South Wales ───────────────────────────────────────────────────────
    { suburb: "Circular Quay", postcode: "2000", state: "NSW" },
    { suburb: "Sydney", postcode: "2000", state: "NSW" },
    { suburb: "Pyrmont", postcode: "2009", state: "NSW" },
    { suburb: "Kings Cross", postcode: "2011", state: "NSW" },
    { suburb: "Waterloo", postcode: "2017", state: "NSW" },
    { suburb: "Mascot", postcode: "2020", state: "NSW" },
    { suburb: "Bondi Junction", postcode: "2022", state: "NSW" },
    { suburb: "North Sydney", postcode: "2060", state: "NSW" },
    { suburb: "Artarmon", postcode: "2064", state: "NSW" },
    { suburb: "Hornsby", postcode: "2077", state: "NSW" },
    { suburb: "Dee Why", postcode: "2099", state: "NSW" },
    { suburb: "West Ryde", postcode: "2114", state: "NSW" },
    { suburb: "Croydon", postcode: "2132", state: "NSW" },
    { suburb: "North Parramatta", postcode: "2150", state: "NSW" },
    { suburb: "Castle Hill", postcode: "2154", state: "NSW" },
    { suburb: "Bexley", postcode: "2207", state: "NSW" },
    { suburb: "Revesby", postcode: "2212", state: "NSW" },
    { suburb: "Hurstville", postcode: "2220", state: "NSW" },
    { suburb: "Taren Point", postcode: "2229", state: "NSW" },
    { suburb: "Hamilton North", postcode: "2292", state: "NSW" },
    { suburb: "Newcastle", postcode: "2292", state: "NSW" },
    { suburb: "Williamtown", postcode: "2318", state: "NSW" },
    { suburb: "Tamworth", postcode: "2340", state: "NSW" },
    { suburb: "Armidale", postcode: "2350", state: "NSW" },
    { suburb: "Narrabri", postcode: "2390", state: "NSW" },
    { suburb: "Moree", postcode: "2400", state: "NSW" },
    { suburb: "Port Macquarie", postcode: "2444", state: "NSW" },
    { suburb: "Coffs Harbour", postcode: "2450", state: "NSW" },
    { suburb: "Glenugie", postcode: "2460", state: "NSW" },
    { suburb: "South Grafton", postcode: "2461", state: "NSW" },
    { suburb: "Grafton", postcode: "2461", state: "NSW" },
    { suburb: "Ballina", postcode: "2478", state: "NSW" },
    { suburb: "Lismore", postcode: "2480", state: "NSW" },
    { suburb: "Tweed Heads", postcode: "2486", state: "NSW" },
    { suburb: "Wollongong", postcode: "2500", state: "NSW" },
    { suburb: "Bomaderry", postcode: "2541", state: "NSW" },
    { suburb: "Nowra", postcode: "2541", state: "NSW" },
    { suburb: "Merimbula", postcode: "2548", state: "NSW" },
    { suburb: "Campbelltown", postcode: "2560", state: "NSW" },
    { suburb: "Goulburn", postcode: "2580", state: "NSW" },
    { suburb: "Albury", postcode: "2640", state: "NSW" },
    { suburb: "Wagga Wagga", postcode: "2650", state: "NSW" },
    { suburb: "Forest Hill", postcode: "2651", state: "NSW" },
    { suburb: "West Wyalong", postcode: "2671", state: "NSW" },
    { suburb: "Griffith", postcode: "2680", state: "NSW" },
    { suburb: "Tumut", postcode: "2720", state: "NSW" },
    { suburb: "Penrith", postcode: "2751", state: "NSW" },
    { suburb: "Raglan", postcode: "2795", state: "NSW" },
    { suburb: "Bathurst", postcode: "2795", state: "NSW" },
    { suburb: "Broken Hill", postcode: "2880", state: "NSW" },

    // ── Northern Territory ────────────────────────────────────────────────────
    { suburb: "Darwin", postcode: "0801", state: "NT" },
    { suburb: "Darwin Airport", postcode: "0820", state: "NT" },
    { suburb: "Alice Springs", postcode: "0870", state: "NT" },
    { suburb: "Yulara", postcode: "0872", state: "NT" },
    { suburb: "Ayers Rock", postcode: "0872", state: "NT" },

    // ── Queensland ────────────────────────────────────────────────────────────
    { suburb: "Brisbane", postcode: "4000", state: "QLD" },
    { suburb: "Fortitude Valley", postcode: "4006", state: "QLD" },
    { suburb: "Eagle Farm", postcode: "4007", state: "QLD" },
    { suburb: "Brisbane Airport", postcode: "4007", state: "QLD" },
    { suburb: "Boondall", postcode: "4034", state: "QLD" },
    { suburb: "Rocklea", postcode: "4106", state: "QLD" },
    { suburb: "Woodridge", postcode: "4114", state: "QLD" },
    { suburb: "Logan", postcode: "4114", state: "QLD" },
    { suburb: "Capalaba", postcode: "4157", state: "QLD" },
    { suburb: "Nerang", postcode: "4211", state: "QLD" },
    { suburb: "Surfers Paradise", postcode: "4217", state: "QLD" },
    { suburb: "Gold Coast", postcode: "4217", state: "QLD" },
    { suburb: "Bilinga", postcode: "4225", state: "QLD" },
    { suburb: "Gold Coast Airport", postcode: "4225", state: "QLD" },
    { suburb: "Ipswich", postcode: "4305", state: "QLD" },
    { suburb: "Toowoomba", postcode: "4350", state: "QLD" },
    { suburb: "Wellcamp", postcode: "4350", state: "QLD" },
    { suburb: "Dalby", postcode: "4405", state: "QLD" },
    { suburb: "Chinchilla", postcode: "4413", state: "QLD" },
    { suburb: "Miles", postcode: "4415", state: "QLD" },
    { suburb: "Roma", postcode: "4455", state: "QLD" },
    { suburb: "Charleville", postcode: "4470", state: "QLD" },
    { suburb: "Strathpine", postcode: "4500", state: "QLD" },
    { suburb: "Maroochydore", postcode: "4558", state: "QLD" },
    { suburb: "Noosaville", postcode: "4566", state: "QLD" },
    { suburb: "Noosa", postcode: "4567", state: "QLD" },
    { suburb: "Hervey Bay", postcode: "4655", state: "QLD" },
    { suburb: "Urangan", postcode: "4655", state: "QLD" },
    { suburb: "Bundaberg", postcode: "4670", state: "QLD" },
    { suburb: "Gladstone", postcode: "4680", state: "QLD" },
    { suburb: "Rockhampton", postcode: "4700", state: "QLD" },
    { suburb: "Biloela", postcode: "4715", state: "QLD" },
    { suburb: "Thangool", postcode: "4716", state: "QLD" },
    { suburb: "Emerald", postcode: "4720", state: "QLD" },
    { suburb: "Longreach", postcode: "4730", state: "QLD" },
    { suburb: "Mackay", postcode: "4740", state: "QLD" },
    { suburb: "East Mackay", postcode: "4740", state: "QLD" },
    { suburb: "Moranbah", postcode: "4744", state: "QLD" },
    { suburb: "Gunyarra", postcode: "4800", state: "QLD" },
    { suburb: "Proserpine", postcode: "4800", state: "QLD" },
    { suburb: "Airlie Beach", postcode: "4802", state: "QLD" },
    { suburb: "Garbutt", postcode: "4814", state: "QLD" },
    { suburb: "Townsville", postcode: "4814", state: "QLD" },
    { suburb: "Mount Isa", postcode: "4825", state: "QLD" },
    { suburb: "Mt Isa", postcode: "4825", state: "QLD" },
    { suburb: "Cairns", postcode: "4870", state: "QLD" },
    { suburb: "Port Douglas", postcode: "4871", state: "QLD" },
    { suburb: "Palm Cove", postcode: "4879", state: "QLD" },

    // ── South Australia ───────────────────────────────────────────────────────
    { suburb: "Adelaide", postcode: "5000", state: "SA" },
    { suburb: "Naracoorte", postcode: "5271", state: "SA" },
    { suburb: "Wandilo", postcode: "5291", state: "SA" },
    { suburb: "Mount Gambier", postcode: "5291", state: "SA" },
    { suburb: "Mullaquana", postcode: "5601", state: "SA" },
    { suburb: "Whyalla", postcode: "5601", state: "SA" },
    { suburb: "North Shields", postcode: "5607", state: "SA" },
    { suburb: "Port Lincoln", postcode: "5607", state: "SA" },
    { suburb: "Ceduna", postcode: "5690", state: "SA" },
    { suburb: "Port Augusta", postcode: "5700", state: "SA" },
    { suburb: "Coober Pedy", postcode: "5723", state: "SA" },
    { suburb: "Olympic Dam", postcode: "5725", state: "SA" },
    { suburb: "Adelaide Airport", postcode: "5950", state: "SA" },

    // ── Tasmania ──────────────────────────────────────────────────────────────
    { suburb: "Hobart", postcode: "7000", state: "TAS" },
    { suburb: "Cambridge", postcode: "7170", state: "TAS" },
    { suburb: "Hobart Airport", postcode: "7170", state: "TAS" },
    { suburb: "Western Junction", postcode: "7212", state: "TAS" },
    { suburb: "Launceston Airport", postcode: "7212", state: "TAS" },
    { suburb: "Launceston", postcode: "7250", state: "TAS" },
    { suburb: "Devonport", postcode: "7307", state: "TAS" },
    { suburb: "East Devonport", postcode: "7310", state: "TAS" },
    { suburb: "Burnie", postcode: "7325", state: "TAS" },
    { suburb: "Wynyard", postcode: "7325", state: "TAS" },

    // ── Victoria ──────────────────────────────────────────────────────────────
    { suburb: "Melbourne", postcode: "3000", state: "VIC" },
    { suburb: "Southbank", postcode: "3006", state: "VIC" },
    { suburb: "South Melbourne", postcode: "3006", state: "VIC" },
    { suburb: "Brooklyn", postcode: "3012", state: "VIC" },
    { suburb: "Footscray", postcode: "3012", state: "VIC" },
    { suburb: "Ravenhall", postcode: "3023", state: "VIC" },
    { suburb: "Caroline Springs", postcode: "3023", state: "VIC" },
    { suburb: "Essendon Fields", postcode: "3041", state: "VIC" },
    { suburb: "Essendon", postcode: "3041", state: "VIC" },
    { suburb: "Airport West", postcode: "3042", state: "VIC" },
    { suburb: "Melbourne Airport", postcode: "3045", state: "VIC" },
    { suburb: "Tullamarine", postcode: "3045", state: "VIC" },
    { suburb: "Preston", postcode: "3072", state: "VIC" },
    { suburb: "Richmond", postcode: "3121", state: "VIC" },
    { suburb: "Camberwell", postcode: "3124", state: "VIC" },
    { suburb: "Blackburn", postcode: "3130", state: "VIC" },
    { suburb: "South Yarra", postcode: "3141", state: "VIC" },
    { suburb: "Bayswater", postcode: "3153", state: "VIC" },
    { suburb: "Bentleigh East", postcode: "3165", state: "VIC" },
    { suburb: "Dandenong", postcode: "3175", state: "VIC" },
    { suburb: "Brighton", postcode: "3185", state: "VIC" },
    { suburb: "Frankston", postcode: "3199", state: "VIC" },
    { suburb: "Avalon", postcode: "3212", state: "VIC" },
    { suburb: "Belmont", postcode: "3220", state: "VIC" },
    { suburb: "Geelong", postcode: "3220", state: "VIC" },
    { suburb: "Warrnambool", postcode: "3280", state: "VIC" },
    { suburb: "Hamilton", postcode: "3300", state: "VIC" },
    { suburb: "Cashmore", postcode: "3305", state: "VIC" },
    { suburb: "Portland", postcode: "3305", state: "VIC" },
    { suburb: "Melton", postcode: "3337", state: "VIC" },
    { suburb: "Wendouree", postcode: "3350", state: "VIC" },
    { suburb: "Ballarat", postcode: "3350", state: "VIC" },
    { suburb: "Horsham", postcode: "3400", state: "VIC" },
    { suburb: "Kyneton", postcode: "3444", state: "VIC" },
    { suburb: "Castlemaine", postcode: "3450", state: "VIC" },
    { suburb: "Mildura", postcode: "3500", state: "VIC" },
    { suburb: "White Hills", postcode: "3550", state: "VIC" },
    { suburb: "Bendigo", postcode: "3550", state: "VIC" },
    { suburb: "Shepparton", postcode: "3630", state: "VIC" },
    { suburb: "Mornington", postcode: "3930", state: "VIC" },
    { suburb: "Rosebud", postcode: "3939", state: "VIC" },

    // ── Western Australia ─────────────────────────────────────────────────────
    { suburb: "Perth", postcode: "6000", state: "WA" },
    { suburb: "Osborne Park", postcode: "6017", state: "WA" },
    { suburb: "Midvale", postcode: "6056", state: "WA" },
    { suburb: "Midland", postcode: "6056", state: "WA" },
    { suburb: "Wangara", postcode: "6065", state: "WA" },
    { suburb: "Malaga", postcode: "6090", state: "WA" },
    { suburb: "Redcliffe", postcode: "6104", state: "WA" },
    { suburb: "Perth Airport", postcode: "6105", state: "WA" },
    { suburb: "Welshpool", postcode: "6106", state: "WA" },
    { suburb: "Fremantle", postcode: "6162", state: "WA" },
    { suburb: "Bunbury", postcode: "6230", state: "WA" },
    { suburb: "Busselton", postcode: "6280", state: "WA" },
    { suburb: "Drome", postcode: "6330", state: "WA" },
    { suburb: "Albany", postcode: "6330", state: "WA" },
    { suburb: "Kalgoorlie", postcode: "6430", state: "WA" },
    { suburb: "Broadwood", postcode: "6430", state: "WA" },
    { suburb: "Leinster", postcode: "6437", state: "WA" },
    { suburb: "Leonora", postcode: "6438", state: "WA" },
    { suburb: "Gibson", postcode: "6448", state: "WA" },
    { suburb: "Esperance", postcode: "6450", state: "WA" },
    { suburb: "Geraldton", postcode: "6530", state: "WA" },
    { suburb: "Carnarvon", postcode: "6701", state: "WA" },
    { suburb: "Exmouth", postcode: "6707", state: "WA" },
    { suburb: "Learmonth", postcode: "6707", state: "WA" },
    { suburb: "Onslow", postcode: "6710", state: "WA" },
    { suburb: "Karratha", postcode: "6714", state: "WA" },
    { suburb: "Gap Ridge", postcode: "6714", state: "WA" },
    { suburb: "Port Hedland", postcode: "6721", state: "WA" },
    { suburb: "Broome", postcode: "6725", state: "WA" },
    { suburb: "Kununurra", postcode: "6743", state: "WA" },
    { suburb: "Newman", postcode: "6753", state: "WA" },
    { suburb: "Paraburdoo", postcode: "6754", state: "WA" },
];

// ── Search function — used directly in the suburbs API route ──────────────────
export function searchSuburbs(query: string, limit = 8) {
    if (!query || query.length < 2) return [];
    const q = query.toLowerCase().trim();

    const results: { suburb: string; postcode: string; state: string; display: string }[] = [];
    const seen = new Set<string>();

    for (const entry of AU_SUBURBS) {
        const suburbMatch = entry.suburb.toLowerCase().startsWith(q);
        const postcodeMatch = entry.postcode.startsWith(q);
        const anyMatch = entry.suburb.toLowerCase().includes(q);

        // Priority 1: suburb starts with query, or postcode starts with query
        // Priority 2: suburb contains query anywhere
        if (suburbMatch || postcodeMatch || anyMatch) {
            const key = `${entry.postcode}-${entry.suburb}`;
            if (seen.has(key)) continue;
            seen.add(key);

            results.push({
                suburb: entry.suburb,
                postcode: entry.postcode,
                state: entry.state,
                display: `${entry.postcode} - ${entry.suburb}, ${entry.state}`,
            });

            if (results.length >= limit) break;
        }
    }

    // Sort: exact postcode match and suburb-starts-with come first
    return results.sort((a, b) => {
        const aExact = a.suburb.toLowerCase().startsWith(q) || a.postcode.startsWith(q) ? 0 : 1;
        const bExact = b.suburb.toLowerCase().startsWith(q) || b.postcode.startsWith(q) ? 0 : 1;
        return aExact - bExact;
    });
}