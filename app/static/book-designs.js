/* Immutable edition recipe; unknown/older editions retain the original layout. */
const bookDesigns = {
 classic:{label:'A MEMORYWEAVER TRAVEL JOURNAL',intro:'Let the journey unfold.',note:'Little moments. Lasting memories.',end:'Some journeys stay with us.'},
 quiet:{label:'FIELD NOTES / A JOURNEY IN STILLNESS',intro:'The beauty of taking our time.',note:'Space to look. Time to remember.',end:'A quiet moment, kept forever.'},
 editorial:{label:'THE TRAVEL EDIT / MEMORYWEAVER',intro:'An eye for the little things.',note:'A collection of passing impressions.',end:'There is always another page.'},
 urban:{label:'CITY JOURNAL / MEMORYWEAVER',intro:'Every block, another story.',note:'On foot. Eyes up. Our own pace.',end:'Keep moving. Keep the memories.'},
 coastal:{label:'COASTAL NOTES / MEMORYWEAVER',intro:'A little closer to the sea.',note:'Sea air. Open horizons. Days together.',end:'Meet me where the island turns blue.'}
};
const designFor = r => Object.hasOwn(bookDesigns,r?.album?.design) ? r.album.design : 'classic';
