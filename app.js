const API_BASE = "/api";
const LOCAL_STORAGE_KEY = "paladins-vault-local-deck";
const PLAYTEST_STORAGE_KEY = "paladins-vault-playtest-session";
const PLAYTEST_STORAGE_BACKUP_KEY = "paladins-vault-playtest-session-backup";
const PROFILE_STORAGE_KEY = "paladins-vault-active-profile";
const BUILDER_PREFS_KEY = "paladins-vault-builder-prefs";
const COOKIE_CONSENT_KEY = "paladins-vault-cookie-consent";
const DEFAULT_LOGO_URL = "/assets/assets/crystal-vault-logo.png";
const PLAYTEST_CARD_BACK_FILE = "playtest-card-back.webp";
const PLAYTEST_BALLOM_VIDEO_FILE = "ballom-evolve-destroy.mp4";
const PLAYTEST_CRYSTAL_PALADIN_VIDEO_FILE = "crystal-paladin-evolve.mp4";
const PLAYTEST_ALCADEIAS_VIDEO_FILE = "alcadeias-evolve.mp4";
const PROFILE_CACHE_KEY = "paladins-vault-active-profile-cache";
const AVATAR_PRESETS = {
  Water: ["Aqua Guard", "Aqua Hulcus", "Emeral", "Crystal Paladin", "Aqua Sniper", "King Tsunami"],
  Darkness: ["Marrow Ooze, the Twister", "Propeller Mutant", "Phantasmal Horror Gigazald", "Deathliger, Lion of Chaos", "Ballom, Master of Death", "Super Necrodragon Abzo Dolba"],
  Light: ["La Ura Giga", "Sarius, Vizier of Suppression", "Craze Valkyrie, the Drastic", "Urth, Purifying Elemental", "Miar, Comet Elemental", "Alcadeias, Lord of Spirits"],
  Nature: ["Bronze-Arm Tribe", "Quixotic Hero Swine Snout", "Charmilia, the Enticer", "Super Terradragon Bailas Gale", "Fighter Dual Fang"],
  Fire: ["Deadly Fighter Braid Claw", "Brawler Zyler", "Armored Blaster Valdios", "Bolshack Dragon", "Bolmeteus Steel Dragon", "Billion-Degree Dragon"],
  Multicivilization: ["Bombazar, Dragon of Destiny", "Death Phoenix, Avatar of Doom", "Wise Starnoid, Avatar of Hope", "Aura Pegasus, Avatar of Life", "Aura Phoenix, Avatar of Destiny"]
};
const AVATAR_PRESET_FOCUS = {
  "aqua guard": { x: 50, y: 24, zoom: 205 },
  "aqua hulcus": { x: 52, y: 24, zoom: 235 },
  "emeral": { x: 50, y: 23, zoom: 235 },
  "crystal paladin": { x: 52, y: 24, zoom: 240 },
  "aqua sniper": { x: 49, y: 23, zoom: 240 },
  "king tsunami": { x: 52, y: 22, zoom: 235 },
  "marrow ooze the twister": { x: 50, y: 24, zoom: 210 },
  "propeller mutant": { x: 50, y: 23, zoom: 210 },
  "phantasmal horror gigazald": { x: 50, y: 22, zoom: 210 },
  "deathliger lion of chaos": { x: 50, y: 24, zoom: 240 },
  "ballom master of death": { x: 50, y: 18, zoom: 250 },
  "super necrodragon abzo dolba": { x: 50, y: 20, zoom: 245 },
  "la ura giga": { x: 50, y: 24, zoom: 240 },
  "sarius vizier of suppression": { x: 50, y: 24, zoom: 240 },
  "craze valkyrie the drastic": { x: 50, y: 23, zoom: 240 },
  "urth purifying elemental": { x: 50, y: 22, zoom: 240 },
  "miar comet elemental": { x: 50, y: 22, zoom: 240 },
  "alcadeias lord of spirits": { x: 50, y: 20, zoom: 245 },
  "bronze arm tribe": { x: 49, y: 24, zoom: 235 },
  "quixotic hero swine snout": { x: 52, y: 23, zoom: 235 },
  "charmilia the enticer": { x: 50, y: 24, zoom: 240 },
  "super terradragon bailas gale": { x: 50, y: 20, zoom: 245 },
  "fighter dual fang": { x: 50, y: 20, zoom: 245 },
  "deadly fighter braid claw": { x: 50, y: 24, zoom: 240 },
  "brawler zyler": { x: 50, y: 24, zoom: 240 },
  "armored blaster valdios": { x: 50, y: 20, zoom: 245 },
  "bolshack dragon": { x: 50, y: 20, zoom: 245 },
  "bolmeteus steel dragon": { x: 50, y: 21, zoom: 212 },
  "billion degree dragon": { x: 50, y: 20, zoom: 245 },
  "bombazar dragon of destiny": { x: 50, y: 19, zoom: 248 },
  "death phoenix avatar of doom": { x: 50, y: 19, zoom: 248 },
  "wise starnoid avatar of hope": { x: 50, y: 21, zoom: 240 },
  "aura pegasus avatar of life": { x: 50, y: 20, zoom: 244 },
  "aura phoenix avatar of destiny": { x: 50, y: 19, zoom: 246 }
};

const page = document.body.dataset.page ?? "welcome";
const isBuilderLandingPage = page === "builder";
const isDeckEditorPage = page === "deck-editor";
const isCardDetailPage = page === "card-detail";
const isHistoryPage = page === "history";
const isPlaytestPage = page === "playtest";
const isPlaymodePage = page === "playmode";
const isBuilderExperiencePage = isBuilderLandingPage || isDeckEditorPage;
const hasPreloadedBuilderDeck = window.location.pathname.match(/^\/share\/[a-z0-9-]+$/i)
  || (isDeckEditorPage && new URLSearchParams(window.location.search).has("deck"));

const state = {
  cards: [],
  allCards: [],
  cardIndex: {},
  profiles: [],
  profileDecks: [],
  likedDecks: [],
  exploreDecks: [],
  notifications: [],
  adminOverview: null,
  activeProfileDetail: null,
  viewedProfile: null,
  activeProfileId: null,
  loadedShareId: null,
  filters: {
    search: "",
    civilization: "all",
    type: "all",
    maxCost: 14
  },
  exploreSearch: "",
  exploreDeckFilters: {
    containsCard: "",
    owner: "",
    civilization: "all"
  },
  filterDefaults: {
    maxCost: 14
  },
  builderView: "image",
  builderSort: "mana",
  deckVisibility: "public",
  deckCoverImageUrl: null,
  builderReady: isBuilderLandingPage ? false : (isDeckEditorPage ? true : Boolean(hasPreloadedBuilderDeck)),
  builderModifyOpen: false,
  historyOpen: false,
  avatarPickerTarget: null,
  deckOwnerId: null,
  loadedDeckOwner: null,
  loadedDeckLikeCount: 0,
  loadedDeckLikedByViewer: false,
  deckReadOnly: false,
  hasUnsavedProfileChanges: false,
  autosaveInFlight: false,
  autosaveQueued: false,
  deckDirtyToken: 0,
  pendingChangeNote: null,
  deckHistory: [],
  deleteDeckTarget: null,
  deck: {},
  cardsLoaded: false,
  selectedSearchCardId: null,
  cardSearchDebounce: null,
  cardsRequestId: 0,
  playtest: {
    title: "Playtest Sandbox",
    coverImage: null,
    ownerLabel: "Paladin's Vault",
    sourceCards: [],
    drawPile: [],
    hand: [],
    shields: [],
    mana: [],
    manaPool: [],
    battle: [],
    graveyard: [],
    turn: 1,
    ready: false
  },
  playtestSelected: null,
  playtestEvolutionPick: null,
  playmodeMatches: [],
  playmodeMatch: null
};

const elements = {
  cardCount: document.querySelector("#card-count"),
  deckCount: document.querySelector("#deck-count"),
  averageCost: document.querySelector("#average-cost"),
  builderStatsSection: document.querySelector("[data-builder-stats]"),
  builderEntryPanel: document.querySelector("#builder-entry-panel"),
  builderEntryStatus: document.querySelector("#builder-entry-status"),
  builderEditorSections: [...document.querySelectorAll("[data-builder-editor]")],
  deckTestingPanels: [...document.querySelectorAll(".deck-testing-panel")],
  newDeckButton: document.querySelector("#new-deck-button"),
  modifyDeckButton: document.querySelector("#modify-deck-button"),
  modifyDeckPanel: document.querySelector("#modify-deck-panel"),
  builderDeckSelect: document.querySelector("#builder-deck-select"),
  loadExistingDeckButton: document.querySelector("#load-existing-deck-button"),
  cancelModifyDeckButton: document.querySelector("#cancel-modify-deck-button"),
  exportSelect: document.querySelector("#export-select"),
  openPlaytestButton: document.querySelector("#open-playtest-button"),
  openAdminPlaytestButton: document.querySelector("#open-admin-playtest-button"),
  openPlaymodePageButton: document.querySelector("#open-playmode-page-button"),
  builderViewSelect: document.querySelector("#builder-view-select"),
  deckCoverSelect: document.querySelector("#deck-cover-select"),
  deckWorkspaceTitle: document.querySelector("#deck-workspace-title"),
  deckBackgroundField: document.querySelector("#deck-background-field"),
  toggleHistoryButton: document.querySelector("#toggle-history-button"),
  deckHistoryPanel: document.querySelector("#deck-history-panel"),
  deckOwnerPanel: document.querySelector("#deck-owner-panel"),
  deckOwnerAvatar: document.querySelector("#deck-owner-avatar"),
  deckOwnerName: document.querySelector("#deck-owner-name"),
  deckOwnerMeta: document.querySelector("#deck-owner-meta"),
  deckOwnerFollowButton: document.querySelector("#deck-owner-follow-button"),
  deckOwnerLikeButton: document.querySelector("#deck-owner-like-button"),
  deckVisibilitySelect: document.querySelector("#deck-visibility-select"),
  builderSortSelect: document.querySelector("#builder-sort"),
  searchInput: document.querySelector("#search-input"),
  searchSuggestions: document.querySelector("#search-suggestions"),
  selectedSearchCard: document.querySelector("#selected-search-card"),
  civilizationFilter: document.querySelector("#civilization-filter"),
  typeFilter: document.querySelector("#type-filter"),
  costFilter: document.querySelector("#cost-filter"),
  costFilterValue: document.querySelector("#cost-filter-value"),
  catalogGrid: document.querySelector("#catalog-grid"),
  deckList: document.querySelector("#deck-list"),
  printDeckSelect: document.querySelector("#print-deck-select"),
  civilizationBreakdown: document.querySelector("#civilization-breakdown"),
  manaCurve: document.querySelector("#mana-curve"),
  printPages: document.querySelector("#print-pages"),
  cardTemplate: document.querySelector("#card-template"),
  deckRowTemplate: document.querySelector("#deck-row-template"),
  cardDetailLayout: document.querySelector("#card-detail-layout"),
  cardDetailEmpty: document.querySelector("#card-detail-empty"),
  cardDetailTitle: document.querySelector("#card-detail-title"),
  cardDetailSubtitle: document.querySelector("#card-detail-subtitle"),
  cardDetailImage: document.querySelector("#card-detail-image"),
  cardDetailName: document.querySelector("#card-detail-name"),
  cardDetailCost: document.querySelector("#card-detail-cost"),
  cardDetailCivs: document.querySelector("#card-detail-civs"),
  cardDetailType: document.querySelector("#card-detail-type"),
  cardDetailRace: document.querySelector("#card-detail-race"),
  cardDetailPower: document.querySelector("#card-detail-power"),
  cardDetailRarity: document.querySelector("#card-detail-rarity"),
  cardDetailText: document.querySelector("#card-detail-text"),
  cardDetailSet: document.querySelector("#card-detail-set"),
  cardDetailNumber: document.querySelector("#card-detail-number"),
  cardDetailIllustrator: document.querySelector("#card-detail-illustrator"),
  cardDetailFlavorWrap: document.querySelector("#card-detail-flavor-wrap"),
  cardDetailFlavor: document.querySelector("#card-detail-flavor"),
  resetFiltersButton: document.querySelector("#reset-filters-button"),
  clearDeckButton: document.querySelector("#clear-deck-button"),
  saveDeckButton: document.querySelector("#save-deck-button"),
  importDeckInput: document.querySelector("#import-deck-input"),
  generatePrintButton: document.querySelector("#generate-print-button"),
  windowPrintButton: document.querySelector("#window-print-button"),
  deckTitleInput: document.querySelector("#deck-title-input"),
  deckWorkspacePanel: document.querySelector(".deck-workspace"),
  pdfExportLink: document.querySelector("#pdf-export-link"),
  printPdfExportLink: document.querySelector("#print-pdf-export-link"),
  shareStatus: document.querySelector("#share-status"),
  deckHistoryList: document.querySelector("#deck-history-list"),
  newProfileName: document.querySelector("#new-profile-name"),
  profileUsernameInput: document.querySelector("#profile-username-input"),
  saveProfileUsernameButton: document.querySelector("#save-profile-username-button"),
  registerEmail: document.querySelector("#register-email"),
  registerAvatarUrl: document.querySelector("#register-avatar-url"),
  openRegisterAvatarPicker: document.querySelector("#open-register-avatar-picker"),
  registerAvatarPreview: document.querySelector("#register-avatar-preview"),
  registerPassword: document.querySelector("#register-password"),
  createProfileButton: document.querySelector("#create-profile-button"),
  profileAvatarUrlInput: document.querySelector("#profile-avatar-url"),
  openProfileAvatarPicker: document.querySelector("#open-profile-avatar-picker"),
  profileAvatarPreview: document.querySelector("#profile-avatar-preview"),
  saveProfileAvatarButton: document.querySelector("#save-profile-avatar-button"),
  avatarPickerModal: document.querySelector("#avatar-picker-modal"),
  avatarPickerBrowser: document.querySelector("#avatar-picker-browser"),
  closeAvatarPicker: document.querySelector("#close-avatar-picker"),
  closeAvatarModalTargets: [...document.querySelectorAll("[data-close-avatar-modal]")],
  authModal: document.querySelector("#auth-modal"),
  closeAuthModal: document.querySelector("#close-auth-modal"),
  closeAuthModalTargets: [...document.querySelectorAll("[data-close-auth-modal]")],
  openAuthModalButtons: [...document.querySelectorAll("[data-open-auth-modal]")],
  resendVerificationButton: document.querySelector("#resend-verification-button"),
  signupModal: document.querySelector("#signup-modal"),
  closeSignupModal: document.querySelector("#close-signup-modal"),
  closeSignupModalTargets: [...document.querySelectorAll("[data-close-signup-modal]")],
  deckDeleteModal: document.querySelector("#deck-delete-modal"),
  closeDeckDeleteModal: document.querySelector("#close-deck-delete-modal"),
  closeDeckDeleteTargets: [...document.querySelectorAll("[data-close-deck-delete-modal]")],
  confirmDeckDeleteButton: document.querySelector("#confirm-deck-delete-button"),
  deckDeleteMessage: document.querySelector("#deck-delete-message"),
  openAccountDeleteModalButton: document.querySelector("#open-account-delete-modal"),
  loginEmail: document.querySelector("#login-email"),
  loginPassword: document.querySelector("#login-password"),
  loginButton: document.querySelector("#login-button"),
  logoutButton: document.querySelector("#logout-button"),
  authLoggedOutSections: [...document.querySelectorAll("[data-auth-logged-out]")],
  authLoggedInSections: [...document.querySelectorAll("[data-auth-logged-in]")],
  profileDisplayName: document.querySelector("#profile-display-name"),
  profilePageTitle: document.querySelector("#profile-page-title"),
  profilePageDescription: document.querySelector("#profile-page-description"),
  profileHandle: document.querySelector("#profile-handle"),
  profileBio: document.querySelector("#profile-bio"),
  profileDeckCount: document.querySelector("#profile-deck-count"),
  profileCardTotal: document.querySelector("#profile-card-total"),
  profileFollowerCount: document.querySelector("#profile-follower-count"),
  profileFollowingCount: document.querySelector("#profile-following-count"),
  followingList: document.querySelector("#following-list"),
  exploreProfileCard: document.querySelector("#explore-profile-card"),
  exploreProfileTitle: document.querySelector("#explore-profile-title"),
  exploreProfileMeta: document.querySelector("#explore-profile-meta"),
  followProfileButton: document.querySelector("#follow-profile-button"),
  profileDecks: document.querySelector("#profile-decks"),
  profileDecksTitle: document.querySelector("#profile-decks-title"),
  likedDecks: document.querySelector("#liked-decks"),
  likedDecksTitle: document.querySelector("#liked-decks-title"),
  exploreDecks: document.querySelector("#explore-decks"),
  exploreUsers: document.querySelector("#explore-users"),
  exploreTypeSelect: document.querySelector("#explore-type-select"),
  exploreSearchInput: document.querySelector("#explore-search-input"),
  openExploreFiltersButton: document.querySelector("#open-explore-filters"),
  exploreFiltersModal: document.querySelector("#explore-filters-modal"),
  closeExploreFiltersButton: document.querySelector("#close-explore-filters"),
  closeExploreFiltersTargets: [...document.querySelectorAll("[data-close-explore-filters]")],
  applyExploreFiltersButton: document.querySelector("#apply-explore-filters"),
  resetExploreFiltersButton: document.querySelector("#reset-explore-filters"),
  exploreFilterCardInput: document.querySelector("#explore-filter-card"),
  exploreFilterOwnerInput: document.querySelector("#explore-filter-owner"),
  exploreFilterCivilizationSelect: document.querySelector("#explore-filter-civilization"),
  exploreDecksPanel: document.querySelector("#explore-decks-panel"),
  exploreUsersPanel: document.querySelector("#explore-users-panel"),
  profileAvatar: document.querySelector("#profile-avatar"),
  routeLinks: [...document.querySelectorAll("[data-route-link]")],
  loginNavLinks: [...document.querySelectorAll("[data-login-nav]")],
  profileMenus: [...document.querySelectorAll("[data-profile-menu]")],
  navAvatars: [...document.querySelectorAll("[data-nav-avatar]")],
  myDecksLinks: [...document.querySelectorAll("[data-my-decks-link]")],
  signupNavLinks: [...document.querySelectorAll("[data-signup-nav]")],
  logoutNavLinks: [...document.querySelectorAll("[data-logout-nav]")],
  navDropdowns: [...document.querySelectorAll(".nav-dropdown")],
  welcomeMessage: document.querySelector("#welcome-message"),
  welcomePrimaryLink: document.querySelector("#welcome-primary-link"),
  welcomeSecondaryLink: document.querySelector("#welcome-secondary-link"),
  textImportInput: document.querySelector("#text-import-input"),
  textImportButton: document.querySelector("#text-import-button"),
  textImportReplaceButton: document.querySelector("#text-import-replace-button"),
  textImportStatus: document.querySelector("#text-import-status"),
  adminPanel: document.querySelector("#admin-panel"),
  adminDenied: document.querySelector("#admin-denied"),
  adminStatGrid: document.querySelector("#admin-stat-grid"),
  adminUsersByMonth: document.querySelector("#admin-users-by-month"),
  adminDecksByMonth: document.querySelector("#admin-decks-by-month"),
  adminDatabaseTables: document.querySelector("#admin-database-tables"),
  adminEmailDiagnostics: document.querySelector("#admin-email-diagnostics"),
  adminNotifyTarget: document.querySelector("#admin-notify-target"),
  adminNotifyMessage: document.querySelector("#admin-notify-message"),
  adminNotifyButton: document.querySelector("#admin-notify-button"),
  adminEmailTarget: document.querySelector("#admin-email-target"),
  adminEmailManual: document.querySelector("#admin-email-manual"),
  adminEmailSubject: document.querySelector("#admin-email-subject"),
  adminEmailMessage: document.querySelector("#admin-email-message"),
  adminEmailButton: document.querySelector("#admin-email-button"),
  adminUserList: document.querySelector("#admin-user-list"),
  adminDeckList: document.querySelector("#admin-deck-list"),
  adminAuditLog: document.querySelector("#admin-audit-log"),
  adminContactInbox: document.querySelector("#admin-contact-inbox"),
  playtestCoverPanel: document.querySelector("#playtest-cover-panel"),
  playtestOwnerLabel: document.querySelector("#playtest-owner-label"),
  playtestSearchInput: document.querySelector("#playtest-search-input"),
  playtestSearchResults: document.querySelector("#playtest-search-results"),
  playtestTitle: document.querySelector("#playtest-title"),
  playtestSubtitle: document.querySelector("#playtest-subtitle"),
  playtestDrawButton: document.querySelector("#playtest-draw-button"),
  playtestShuffleButton: document.querySelector("#playtest-shuffle-button"),
  playtestResetButton: document.querySelector("#playtest-reset-button"),
  playtestTurnDec: document.querySelector("#playtest-turn-dec"),
  playtestTurnInput: document.querySelector("#playtest-turn-input"),
  playtestTurnInc: document.querySelector("#playtest-turn-inc"),
  playtestExitButton: document.querySelector("#playtest-exit-button"),
  playtestTurnValue: document.querySelector("#playtest-turn-value"),
  playtestDrawCount: document.querySelector("#playtest-draw-count"),
  playtestShieldCount: document.querySelector("#playtest-shield-count"),
  playtestHandCount: document.querySelector("#playtest-hand-count"),
  playtestBattleCount: document.querySelector("#playtest-battle-count"),
  playtestManaCount: document.querySelector("#playtest-mana-count"),
  playtestGraveCount: document.querySelector("#playtest-grave-count"),
  playtestEmpty: document.querySelector("#playtest-empty"),
  playtestBoard: document.querySelector("#playtest-board"),
  playtestDrawPileZone: document.querySelector("#playtest-draw-pile-zone"),
  playtestShieldsZone: document.querySelector("#playtest-shields-zone"),
  playtestHandZone: document.querySelector("#playtest-hand-zone"),
  playtestBattleZone: document.querySelector("#playtest-battle-zone"),
  playtestManaZone: document.querySelector("#playtest-mana-zone"),
  playtestManaPool: document.querySelector("#playtest-mana-pool"),
  playtestGraveyardZone: document.querySelector("#playtest-graveyard-zone"),
  playtestActionOverlay: null,
  playtestCinematicModal: null,
  playtestCinematicVideo: null,
  playtestLibraryModal: null,
  playtestLibrarySearchInput: null,
  playtestLibrarySearchResults: null,
  closePlaytestLibraryModal: null,
  closePlaytestLibraryModalTargets: [],
  historyPageTitle: document.querySelector("#history-page-title"),
  historyPageSubtitle: document.querySelector("#history-page-subtitle"),
  adminMonthModal: null,
  adminMonthModalTitle: null,
  adminMonthModalLabel: null,
  adminMonthProfilesList: null,
  adminMonthDecksList: null,
  closeAdminMonthModal: null,
  closeAdminMonthModalTargets: [],
  contactUsername: document.querySelector("#contact-username"),
  contactEmail: document.querySelector("#contact-email"),
  contactSubject: document.querySelector("#contact-subject"),
  contactMessage: document.querySelector("#contact-message"),
  contactSubmitButton: document.querySelector("#contact-submit-button"),
  playmodeDenied: document.querySelector("#playmode-denied"),
  playmodePanel: document.querySelector("#playmode-panel"),
  playmodeDeckSelect: document.querySelector("#playmode-deck-select"),
  playmodeModeSelect: document.querySelector("#playmode-mode-select"),
  playmodeCreateButton: document.querySelector("#playmode-create-button"),
  playmodeOpenCode: document.querySelector("#playmode-open-code"),
  playmodeOpenButton: document.querySelector("#playmode-open-button"),
  playmodeList: document.querySelector("#playmode-list"),
  playmodeStatus: document.querySelector("#playmode-status"),
  playmodeJoinPanel: document.querySelector("#playmode-join-panel"),
  playmodeJoinDeckSelect: document.querySelector("#playmode-join-deck-select"),
  playmodeJoinButton: document.querySelector("#playmode-join-button"),
  playmodeBoard: document.querySelector("#playmode-board"),
  playmodeBoardTitle: document.querySelector("#playmode-board-title"),
  playmodeBoardMeta: document.querySelector("#playmode-board-meta"),
  playmodePlayerOne: document.querySelector("#playmode-player-one"),
  playmodePlayerTwo: document.querySelector("#playmode-player-two"),
  statusNodes: [...document.querySelectorAll("[data-status]")]
};

function displayUsername(username) {
  return String(username || "").replace(/^@+/, "");
}

function normalizedUsername(username) {
  return displayUsername(username).toLowerCase();
}

initialize().catch((error) => {
  console.error(error);
  setBootLoadingState(false);
  setStatus("Paladin's Vault could not finish loading. Please check the backend.", "error");
});

async function initialize() {
  setBootLoadingState(true);
  ensureDeckDeleteModal();
  ensureAccountDeleteModal();
  ensureExportModal();
  ensureAdminMonthModal();
  ensureAuthModalEnhancements();
  ensurePlaytestActionOverlay();
  ensurePlaytestCinematicModal();
  ensurePlaytestLibraryModal();
  ensureNotificationMenu();
  ensureMobileNavToggle();
  ensureCookieConsentBanner();
  setActiveNav();
  primeCachedProfileState();
  renderAuthNavigation();
  renderWelcome();
  renderProfile();
  bindEvents();
  if (isPlaytestPage) {
    try {
      await loadPlaytestSandbox();
      renderPlaytestSandbox();
    } finally {
      setBootLoadingState(false);
    }
    if (window.location.protocol !== "file:") {
      void hydrateProfiles()
        .then(() => {
          renderAuthNavigation();
          renderNotifications();
        })
        .catch(() => {});
    }
    return;
  }
  try {
    await hydrateProfiles();
  } catch (error) {
    console.warn("hydrateProfiles failed", error);
  }
  if ((page === "profile" || page === "my-decks") && state.activeProfileId) {
    try {
      await loadProfileDecks(state.activeProfileId);
    } catch (error) {
      console.warn("loadProfileDecks failed", error);
    }
  }
  renderAuthNavigation();
  renderWelcome();
  renderProfile();
  if (page === "my-decks") {
    renderProfileDecks();
  }
  renderContactPage();
  setBootLoadingState(false);
  hydrateBuilderPreferences();
  maybeLoadLocalDeck();
  try {
    await hydrateDeckCards();
  } catch (error) {
    console.warn("hydrateDeckCards failed", error);
  }
  try {
    await maybeLoadSharedDeck();
  } catch (error) {
    console.warn("maybeLoadSharedDeck failed", error);
  }
  try {
    await maybeLoadBuilderDeckFromQuery();
  } catch (error) {
    console.warn("maybeLoadBuilderDeckFromQuery failed", error);
  }
  maybeStartNewDeckFromQuery();
  maybeOpenImportedDeckFromQuery();
  renderWelcome();
  renderAuthNavigation();
  renderProfile();
  renderStatusFromQuery();
  maybeOpenAccountDeleteFromQuery();
  renderBuilderDeckOptions();
  renderBuilderEntry();
  renderPrintDeckOptions();
  renderPlaymodePage();
  renderBuilder();
  renderPrintPages();
  renderHeaderStats();
  renderContactPage();

  const backgroundTasks = [
    (async () => {
      if (!needsCards(page)) {
        return;
      }
      await hydrateFilters();
      const shouldPreloadCards = !isDeckEditorPage || state.filters.search || state.filters.civilization !== "all" || state.filters.type !== "all" || state.filters.maxCost !== state.filterDefaults.maxCost;
      if (shouldPreloadCards) {
        await loadCards(isDeckEditorPage ? 60 : 160);
      }
    })(),
    page === "profile" ? loadAllCards() : Promise.resolve(),
    needsProfileDecks(page) && state.activeProfileId ? loadProfileDecks(state.activeProfileId) : Promise.resolve(),
    state.activeProfileId ? loadNotifications() : Promise.resolve(),
    needsExploreDecks(page) ? loadExploreDecks() : Promise.resolve(),
    page === "profile" ? maybeLoadViewedProfile() : Promise.resolve(),
    isCardDetailPage ? loadCardDetailPage() : Promise.resolve(),
    isHistoryPage ? loadHistoryPage() : Promise.resolve(),
    isPlaymodePage && state.activeProfileId ? loadPlaymodeMatches() : Promise.resolve(),
    isPlaymodePage ? maybeLoadPlaymodeMatchFromQuery() : Promise.resolve(),
    page === "admin" && state.activeProfileId ? loadAdminOverview() : Promise.resolve(),
    state.loadedShareId && state.deckHistory.length === 0 ? loadDeckHistory(state.loadedShareId) : Promise.resolve()
  ];

  Promise.allSettled(backgroundTasks).then(() => {
    renderNotifications();
    renderProfile();
    renderProfileDecks();
    renderExploreDecks();
    renderExploreUsers();
    renderExploreSections();
    renderAvatarPresetChoosers();
    renderCards();
    renderDeckHistory();
    renderPlaytestSandbox();
    renderPlaymodePage();
    renderHeaderStats();
    renderAdminPage();
  });
}

function currentCardDetailId() {
  const match = window.location.pathname.match(/\/cards\/(\d+)$/);
  if (match) {
    return Number(match[1]);
  }
  const queryId = new URLSearchParams(window.location.search).get("id");
  return queryId && /^\d+$/.test(queryId) ? Number(queryId) : null;
}

function openCardDetail(card) {
  if (!card?.id) {
    return;
  }
  if (window.location.protocol === "file:") {
    window.location.assign(`./card-detail.html?id=${encodeURIComponent(card.id)}`);
    return;
  }
  window.location.assign(`/cards/${card.id}`);
}

function playtestPagePath() {
  return window.location.protocol === "file:" ? "./playtest.html" : "/playtest";
}

function playmodePagePath() {
  return window.location.protocol === "file:" ? "./playmode.html" : "/playmode";
}

function historyPagePath() {
  return window.location.protocol === "file:" ? "./history.html" : "/builder/history";
}

function builderEditorPath() {
  return window.location.protocol === "file:" ? "./deck-editor.html" : "/builder/editor";
}

function resolveAssetUrl(path) {
  if (!path) {
    return DEFAULT_LOGO_URL;
  }
  if (/^(https?:)?\/\//i.test(path) || path.startsWith("data:")) {
    return path;
  }
  if (window.location.protocol === "file:" && path.startsWith("/")) {
    return `.${path}`;
  }
  return path;
}

function playtestAssetUrl(filename) {
  if (!filename) {
    return DEFAULT_LOGO_URL;
  }
  if (window.location.protocol === "file:") {
    return `./assets/${filename}`;
  }
  return `/assets/assets/${filename}`;
}

function createPlaytestInstance(card, index) {
  return {
    uid: `${card.id}-${index}-${Math.random().toString(36).slice(2, 8)}`,
    card,
    tapped: false,
    faceDown: false,
    manaProduced: [],
    underlays: []
  };
}

function shuffleArray(items) {
  const next = [...items];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
  }
  return next;
}

function playtestZones() {
  return ["drawPile", "hand", "shields", "mana", "battle", "graveyard"];
}

function emptyPlaytestState(title = "Playtest Sandbox", sourceCards = [], options = {}) {
  return {
    title,
    coverImage: options.coverImage || null,
    ownerLabel: options.ownerLabel || "Paladin's Vault",
    sourceCards,
    drawPile: [],
    hand: [],
    shields: [],
    mana: [],
    manaPool: [],
    battle: [],
    graveyard: [],
    turn: 1,
    ready: false
  };
}

function persistPlaytestState() {
  try {
    window.sessionStorage.setItem(PLAYTEST_STORAGE_KEY, JSON.stringify(state.playtest));
  } catch {}
  try {
    window.localStorage.setItem(PLAYTEST_STORAGE_BACKUP_KEY, JSON.stringify(state.playtest));
  } catch {}
}

function applyPlaytestState(nextState) {
  state.playtest = {
    ...emptyPlaytestState(nextState?.title || "Playtest Sandbox", nextState?.sourceCards || []),
    ...nextState
  };
  if (
    state.playtestSelected
    && !playtestZones().some((zoneName) => (state.playtest[zoneName] || []).some((entry) => entry.uid === state.playtestSelected?.uid))
  ) {
    state.playtestSelected = null;
  }
  persistPlaytestState();
}

function isSpellCard(card) {
  return /\bspell\b/i.test(card?.type || "");
}

function isChargerSpellCard(card) {
  return isSpellCard(card) && /\bcharger\b/i.test(`${card?.name || ""} ${card?.text || ""}`);
}

function isEvolutionCard(card) {
  return /\bevolution\b/i.test(`${card?.type || ""} ${card?.text || ""}`);
}

function normalizePlaytestRequirement(value) {
  return normalizeName(String(value || "")
    .replace(/\bcreatures?\b/gi, "")
    .replace(/\bcards?\b/gi, "")
    .replace(/\bone of your\b/gi, "")
    .replace(/\byour\b/gi, "")
    .replace(/[.,;:()[\]/-]/g, " ")
    .trim());
}

function canonicalPlaytestTokens(value) {
  return normalizePlaytestRequirement(value)
    .split(/\s+/)
    .map((token) => token.replace(/s$/i, ""))
    .filter(Boolean);
}

function extractEvolutionRequirement(card) {
  const text = String(card?.text || "");
  const match = text.match(/put on one of your\s+([^.]+?)(?:\.|$)/i);
  if (!match) {
    return "";
  }
  return normalizePlaytestRequirement(match[1]);
}

function battleCardsEligibleForEvolution(card) {
  const requirement = extractEvolutionRequirement(card);
  const evolutionRace = normalizePlaytestRequirement(card?.race_label || "");
  const requirementTokens = canonicalPlaytestTokens(requirement);
  const evolutionTokens = canonicalPlaytestTokens(evolutionRace);
  return (state.playtest.battle || []).filter((entry) => {
    const candidateRace = normalizePlaytestRequirement(entry.card?.race_label || "");
    const candidateType = normalizePlaytestRequirement(entry.card?.type || "");
    const candidateTokens = new Set([
      ...canonicalPlaytestTokens(candidateRace),
      ...canonicalPlaytestTokens(candidateType)
    ]);
    if (requirement) {
      return requirementTokens.every((token) => candidateTokens.has(token));
    }
    return evolutionTokens.length > 0 && evolutionTokens.every((token) => candidateTokens.has(token));
  });
}

function beginEvolutionPlay(card) {
  const eligible = battleCardsEligibleForEvolution(card.card);
  if (!eligible.length) {
    setStatus(`No valid evolution target is in your Battle Zone for ${card.card.name}.`, "error");
    return;
  }
  state.playtestEvolutionPick = {
    sourceUid: card.uid,
    eligibleUids: eligible.map((entry) => entry.uid)
  };
  state.playtestSelected = null;
  renderPlaytestSandbox();
  setStatus(`Select a Battle Zone card to evolve into ${card.card.name}.`, "info");
}

function completeEvolutionPlay(targetUid) {
  const pick = state.playtestEvolutionPick;
  if (!pick) {
    return;
  }
  const handIndex = state.playtest.hand.findIndex((entry) => entry.uid === pick.sourceUid);
  const battleIndex = state.playtest.battle.findIndex((entry) => entry.uid === targetUid);
  if (handIndex === -1 || battleIndex === -1) {
    state.playtestEvolutionPick = null;
    renderPlaytestSandbox();
    return;
  }
  const evolution = state.playtest.hand[handIndex];
  if (!consumePlaytestMana(evolution.card)) {
    state.playtestEvolutionPick = null;
    setStatus(`You do not have enough charged mana to evolve ${evolution.card.name}.`, "error");
    renderPlaytestSandbox();
    return;
  }
  const [playedEvolution] = state.playtest.hand.splice(handIndex, 1);
  const base = state.playtest.battle[battleIndex];
  state.playtest.battle.splice(battleIndex, 1, {
    ...playedEvolution,
    faceDown: false,
    tapped: false,
    underlays: [
      {
        ...base,
        underlays: []
      },
      ...(base.underlays || []).map((entry) => ({
        ...entry,
        underlays: []
      }))
    ]
  });
  let ballomDestroyed = [];
  if (normalizeName(playedEvolution.card.name) === "ballom master of death") {
    ballomDestroyed = resolveBallomBattlefieldWipe(targetUid);
  }
  state.playtestEvolutionPick = null;
  state.playtestSelected = null;
  persistPlaytestState();
  renderPlaytestSandbox();
  const evolvedName = normalizeName(playedEvolution.card.name);
  if (evolvedName === "ballom master of death") {
    playBallomEvolutionAnimation();
  } else if (evolvedName === "crystal paladin") {
    playCrystalPaladinEvolutionAnimation();
  } else if (evolvedName === "alcadeias lord of spirits") {
    playAlcadeiasEvolutionAnimation();
  }
  if (ballomDestroyed.length) {
    setStatus(`${playedEvolution.card.name} evolved and destroyed ${ballomDestroyed.join(", ")}.`, "success");
  } else {
    setStatus(`${playedEvolution.card.name} evolved successfully.`, "success");
  }
}

function resolveBallomBattlefieldWipe(ballomUid) {
  const survivors = [];
  const destroyed = [];
  for (const entry of state.playtest.battle || []) {
    if (entry.uid === ballomUid) {
      survivors.push(entry);
      continue;
    }
    const civilizations = Array.isArray(entry.card?.civilizations) ? entry.card.civilizations : [];
    const isCreature = /\bcreature\b/i.test(entry.card?.type || "");
    const hasDarkness = civilizations.some((civilization) => normalizeName(civilization) === "darkness");
    if (isCreature && !hasDarkness) {
      state.playtest.graveyard.push({
        ...entry,
        faceDown: false,
        tapped: false
      });
      destroyed.push(entry.card?.name || "Unknown creature");
      continue;
    }
    survivors.push(entry);
  }
  state.playtest.battle = survivors;
  return destroyed;
}

function closePlaytestCinematicModal() {
  const modal = elements.playtestCinematicModal;
  const video = elements.playtestCinematicVideo;
  if (!modal || !video) {
    return;
  }
  modal.classList.remove("is-visible");
  modal.classList.add("is-closing");
  window.setTimeout(() => {
    video.pause();
    video.currentTime = 0;
    modal.hidden = true;
    modal.classList.remove("is-closing");
  }, 340);
}

function playPlaytestCinematic(filename) {
  if (!elements.playtestCinematicModal || !elements.playtestCinematicVideo) {
    return;
  }
  const modal = elements.playtestCinematicModal;
  const video = elements.playtestCinematicVideo;
  modal.hidden = false;
  modal.classList.remove("is-closing");
  modal.classList.remove("is-visible");
  video.pause();
  video.currentTime = 0;
  video.src = playtestAssetUrl(filename);
  requestAnimationFrame(() => {
    modal.classList.add("is-visible");
  });
  const finish = () => {
    video.removeEventListener("ended", finish);
    closePlaytestCinematicModal();
  };
  video.addEventListener("ended", finish, { once: true });
  const playAttempt = video.play();
  if (playAttempt && typeof playAttempt.catch === "function") {
    playAttempt.catch(() => {
      window.setTimeout(closePlaytestCinematicModal, 4500);
    });
  }
}

function playBallomEvolutionAnimation() {
  playPlaytestCinematic(PLAYTEST_BALLOM_VIDEO_FILE);
}

function playCrystalPaladinEvolutionAnimation() {
  playPlaytestCinematic(PLAYTEST_CRYSTAL_PALADIN_VIDEO_FILE);
}

function playAlcadeiasEvolutionAnimation() {
  playPlaytestCinematic(PLAYTEST_ALCADEIAS_VIDEO_FILE);
}

function isShieldTriggerCard(card) {
  return /\bshield\s*trigger\b/i.test(card?.text || "");
}

function buildPlaytestSourceCards() {
  return expandDeckCards().filter(Boolean).map((card) => ({ ...card }));
}

function playtestSourceCardChoices() {
  const seen = new Set();
  return (state.playtest.sourceCards || []).filter((card) => {
    if (!card?.id || seen.has(card.id)) {
      return false;
    }
    seen.add(card.id);
    return true;
  });
}

function playtestCoverImageUrl() {
  return playtestAssetUrl(PLAYTEST_CARD_BACK_FILE);
}

async function ensureDeckCardsHydratedForPlaytest() {
  const missingIds = Object.keys(state.deck).filter((cardId) => state.deck[cardId] > 0 && !state.cardIndex[cardId]);
  if (!missingIds.length || window.location.protocol === "file:") {
    return;
  }
  const payload = await fetchJson(`${API_BASE}/cards/by-ids?ids=${missingIds.join(",")}`);
  for (const card of payload.items || []) {
    state.cardIndex[String(card.id)] = card;
  }
}

function setupPlaytestGame(options = {}) {
  const keepTurn = options.keepTurn === true;
  const deckStack = shuffleArray(state.playtest.sourceCards.map((card, index) => createPlaytestInstance(card, index)));
  const shields = deckStack.splice(0, 5).map((entry) => ({ ...entry, faceDown: true }));
  const hand = deckStack.splice(0, 5).map((entry) => ({ ...entry, faceDown: false }));
  applyPlaytestState({
    ...state.playtest,
    drawPile: deckStack,
    hand,
    shields,
    mana: [],
    manaPool: [],
    battle: [],
    graveyard: [],
    turn: keepTurn ? state.playtest.turn : 1,
    ready: true
  });
  renderPlaytestSandbox();
}

function restartPlaytestGame() {
  state.playtestSelected = null;
  state.playtestEvolutionPick = null;
  setupPlaytestGame({ keepTurn: false });
}

function hardRestartPlaytestGame() {
  restartPlaytestGame();
  try {
    window.sessionStorage.setItem(PLAYTEST_STORAGE_KEY, JSON.stringify(state.playtest));
  } catch {}
  try {
    window.localStorage.setItem(PLAYTEST_STORAGE_BACKUP_KEY, JSON.stringify(state.playtest));
  } catch {}
  window.location.reload();
}

function movePlaytestCard(sourceZone, uid, targetZone, options = {}) {
  const source = state.playtest[sourceZone];
  const target = state.playtest[targetZone];
  if (!Array.isArray(source) || !Array.isArray(target)) {
    return;
  }
  const index = source.findIndex((entry) => entry.uid === uid);
  if (index === -1) {
    return;
  }
  const [card] = source.splice(index, 1);
  if (sourceZone === "mana") {
    clearManaPoolForSource(uid);
  }
  const stackEntries = [card, ...(card.underlays || [])].map((entry) => ({
    ...entry,
    underlays: [],
    tapped: options.resetTapped ? false : Boolean(options.tapped ?? entry.tapped),
    faceDown: typeof options.faceDown === "boolean" ? options.faceDown : entry.faceDown,
    manaProduced: []
  }));
  if (stackEntries.length > 1 && targetZone !== "battle") {
    if (options.toTop) {
      target.unshift(...stackEntries);
    } else {
      target.push(...stackEntries);
    }
  } else {
    const moved = {
      ...card,
      tapped: options.resetTapped ? false : Boolean(options.tapped ?? card.tapped),
      faceDown: typeof options.faceDown === "boolean" ? options.faceDown : card.faceDown,
      manaProduced: []
    };
    if (options.toTop) {
      target.unshift(moved);
    } else {
      target.push(moved);
    }
  }
  state.playtestSelected = null;
  persistPlaytestState();
  renderPlaytestSandbox();
}

function togglePlaytestTapped(zoneName, uid) {
  const zone = state.playtest[zoneName];
  if (!Array.isArray(zone)) {
    return;
  }
  const card = zone.find((entry) => entry.uid === uid);
  if (!card) {
    return;
  }
  if (zoneName === "mana") {
    togglePlaytestManaTap(uid);
    return;
  }
  card.tapped = !card.tapped;
  state.playtestSelected = { zone: zoneName, uid };
  persistPlaytestState();
  renderPlaytestSandbox();
}

function playtestCardCivilizations(card) {
  return Array.isArray(card?.civilizations) ? card.civilizations.filter(Boolean) : [];
}

function playtestCardNeedsCivilization(card) {
  const civilizations = playtestCardCivilizations(card);
  return civilizations.length ? civilizations : [];
}

function clearManaPoolForSource(uid) {
  state.playtest.manaPool = (state.playtest.manaPool || []).filter((entry) => entry.sourceUid !== uid);
}

function addManaFromCard(cardEntry, civilization) {
  if (!cardEntry) {
    return;
  }
  clearManaPoolForSource(cardEntry.uid);
  cardEntry.manaProduced = civilization ? [civilization] : [];
  if (civilization) {
    state.playtest.manaPool.push({
      id: `${cardEntry.uid}-${civilization}`,
      sourceUid: cardEntry.uid,
      civilization
    });
  }
}

function togglePlaytestManaTap(uid, preferredCivilization = null) {
  const zone = state.playtest.mana || [];
  const card = zone.find((entry) => entry.uid === uid);
  if (!card) {
    return;
  }
  if (card.tapped) {
    card.tapped = false;
    card.manaProduced = [];
    clearManaPoolForSource(uid);
  } else {
    const civilizations = playtestCardCivilizations(card.card);
    const chosen = preferredCivilization && civilizations.includes(preferredCivilization)
      ? preferredCivilization
      : (civilizations[0] || null);
    card.tapped = true;
    addManaFromCard(card, chosen);
  }
  state.playtestSelected = { zone: "mana", uid };
  persistPlaytestState();
  renderPlaytestSandbox();
}

function canPayPlaytestCost(card) {
  const pool = state.playtest.manaPool || [];
  const cost = Math.max(0, Number(card?.cost) || 0);
  if (pool.length < cost) {
    return false;
  }
  const requiredCivilizations = playtestCardNeedsCivilization(card);
  if (!requiredCivilizations.length) {
    return true;
  }
  return pool.some((entry) => requiredCivilizations.includes(entry.civilization));
}

function consumePlaytestMana(card) {
  const cost = Math.max(0, Number(card?.cost) || 0);
  if (cost === 0) {
    return true;
  }
  if (!canPayPlaytestCost(card)) {
    return false;
  }
  const pool = [...(state.playtest.manaPool || [])];
  const requiredCivilizations = playtestCardNeedsCivilization(card);
  const used = [];
  if (requiredCivilizations.length) {
    const matchingIndex = pool.findIndex((entry) => requiredCivilizations.includes(entry.civilization));
    if (matchingIndex === -1) {
      return false;
    }
    used.push(pool.splice(matchingIndex, 1)[0]);
  }
  while (used.length < cost && pool.length) {
    used.push(pool.shift());
  }
  state.playtest.manaPool = (state.playtest.manaPool || []).filter(
    (entry) => !used.some((spent) => spent.id === entry.id)
  );
  for (const spent of used) {
    const source = (state.playtest.mana || []).find((entry) => entry.uid === spent.sourceUid);
    if (source) {
      source.manaProduced = [];
    }
  }
  return true;
}

function toggleShieldReveal(uid) {
  const shield = state.playtest.shields.find((entry) => entry.uid === uid);
  if (!shield) {
    return;
  }
  shield.faceDown = !shield.faceDown;
  state.playtestSelected = { zone: "shields", uid };
  persistPlaytestState();
  renderPlaytestSandbox();
}

function drawPlaytestCards(count = 1) {
  const amount = Math.max(1, count);
  for (let index = 0; index < amount; index += 1) {
    if (!state.playtest.drawPile.length) {
      break;
    }
    const nextCard = state.playtest.drawPile.shift();
    state.playtest.hand.push({ ...nextCard, faceDown: false, tapped: false });
  }
  state.playtest.ready = true;
  state.playtestSelected = null;
  state.playtestEvolutionPick = null;
  persistPlaytestState();
  renderPlaytestSandbox();
}

function closePlaytestLibraryModal() {
  if (elements.playtestLibraryModal) {
    elements.playtestLibraryModal.hidden = true;
  }
}

function tutorPlaytestCardFromLibrary(uid) {
  const index = state.playtest.drawPile.findIndex((entry) => entry.uid === uid);
  if (index === -1) {
    return;
  }
  const [card] = state.playtest.drawPile.splice(index, 1);
  state.playtest.hand.push({ ...card, faceDown: false, tapped: false });
  state.playtest.drawPile = shuffleArray(state.playtest.drawPile);
  state.playtestSelected = null;
  state.playtestEvolutionPick = null;
  persistPlaytestState();
  closePlaytestLibraryModal();
  renderPlaytestSandbox();
  setStatus(`Took ${card.card.name} from the library to hand, then shuffled the deck.`, "success");
}

function renderPlaytestLibrarySearchResults() {
  if (!elements.playtestLibrarySearchResults || !elements.playtestLibrarySearchInput) {
    return;
  }
  const container = elements.playtestLibrarySearchResults;
  const query = normalizeName(elements.playtestLibrarySearchInput.value.trim());
  container.replaceChildren();
  const matches = (state.playtest.drawPile || [])
    .filter((entry) => !query || normalizeName(entry.card?.name || "").includes(query))
    .slice(0, 48);
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.className = "hero-text playtest-zone-empty";
    empty.textContent = "No matching cards in the library.";
    container.append(empty);
    return;
  }
  for (const entry of matches) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "playtest-search-result";
    button.innerHTML = `
      <strong>${escapeHtml(entry.card.name)}</strong>
      <span>${escapeHtml(`${entry.card.cost} mana • ${entry.card.type}${entry.card.race_label ? ` • ${entry.card.race_label}` : ""}`)}</span>
    `;
    button.addEventListener("click", () => tutorPlaytestCardFromLibrary(entry.uid));
    container.append(button);
  }
}

function openPlaytestLibrarySearch() {
  if (!elements.playtestLibraryModal) {
    return;
  }
  elements.playtestLibraryModal.hidden = false;
  if (elements.playtestLibrarySearchInput) {
    elements.playtestLibrarySearchInput.value = "";
  }
  renderPlaytestLibrarySearchResults();
  queueMicrotask(() => elements.playtestLibrarySearchInput?.focus());
}

function advancePlaytestTurn() {
  for (const zoneName of ["hand", "shields", "mana", "battle", "graveyard", "drawPile"]) {
    const zone = state.playtest[zoneName];
    if (!Array.isArray(zone)) {
      continue;
    }
    for (const card of zone) {
      card.tapped = false;
      card.manaProduced = [];
    }
  }
  state.playtest.manaPool = [];
  state.playtest.turn = (state.playtest.turn || 1) + 1;
  drawPlaytestCards(1);
}

function renderPlaytestSearchResults() {
  if (!elements.playtestSearchResults || !elements.playtestSearchInput) {
    return;
  }
  const query = elements.playtestSearchInput.value.trim().toLowerCase();
  const container = elements.playtestSearchResults;
  container.replaceChildren();
  if (!query) {
    container.hidden = true;
    return;
  }
  const matches = playtestSourceCardChoices()
    .filter((card) => normalizeName(card.name).includes(normalizeName(query)))
    .slice(0, 8);
  if (!matches.length) {
    container.hidden = true;
    return;
  }
  for (const card of matches) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "playtest-search-result";
    button.innerHTML = `
      <strong>${escapeHtml(card.name)}</strong>
      <span>${escapeHtml(`${card.cost} mana • ${card.type} • ${card.race_label}`)}</span>
    `;
    button.addEventListener("click", () => {
      container.hidden = true;
      openCardDetail(card);
    });
    container.append(button);
  }
  container.hidden = false;
}

function mulliganPlaytestHand() {
  if (!state.playtest.hand.length) {
    return;
  }
  const nextDeck = shuffleArray([
    ...state.playtest.drawPile,
    ...state.playtest.hand.map((entry) => ({ ...entry, faceDown: false, tapped: false }))
  ]);
  const handSize = state.playtest.hand.length;
  state.playtest.drawPile = nextDeck;
  state.playtest.hand = [];
  for (let index = 0; index < handSize; index += 1) {
    if (!state.playtest.drawPile.length) {
      break;
    }
    const card = state.playtest.drawPile.shift();
    state.playtest.hand.push({ ...card, faceDown: false, tapped: false });
  }
  state.playtest.ready = true;
  state.playtestSelected = null;
  persistPlaytestState();
  renderPlaytestSandbox();
}

function zoneLabel(zoneName) {
  return {
    drawPile: "Draw Pile",
    hand: "Hand",
    shields: "Shields",
    mana: "Mana Zone",
    battle: "Battle Zone",
    graveyard: "Graveyard"
  }[zoneName] || zoneName;
}

function renderPlaytestZoneEmpty(container, message) {
  const empty = document.createElement("p");
  empty.className = "hero-text playtest-zone-empty";
  empty.textContent = message;
  container.append(empty);
}

function playtestActionDefinitions(zoneName, card) {
  const actions = [];
  if (zoneName === "hand") {
    const affordable = canPayPlaytestCost(card.card);
    actions.push(
      {
        label: isEvolutionCard(card.card) ? "Evolve" : "Play",
        disabled: !affordable,
        run: () => {
          if (!canPayPlaytestCost(card.card)) {
            setStatus(`You need ${card.card.cost} mana, including ${playtestCardNeedsCivilization(card.card).join(" or ") || "a matching civilization"}, to play ${card.card.name}.`, "error");
            return;
          }
          if (isSpellCard(card.card)) {
            consumePlaytestMana(card.card);
            if (isChargerSpellCard(card.card)) {
              movePlaytestCard("hand", card.uid, "mana", { faceDown: false, resetTapped: true });
              return;
            }
            movePlaytestCard("hand", card.uid, "graveyard", { faceDown: false, resetTapped: true });
            return;
          }
          if (isEvolutionCard(card.card)) {
            beginEvolutionPlay(card);
            return;
          }
          consumePlaytestMana(card.card);
          movePlaytestCard("hand", card.uid, "battle", { faceDown: false, resetTapped: true });
        }
      },
      { label: "Charge", run: () => movePlaytestCard("hand", card.uid, "mana", { faceDown: false, resetTapped: true }) },
      { label: "Discard", run: () => movePlaytestCard("hand", card.uid, "graveyard", { faceDown: false, resetTapped: true }) },
    );
  }
  if (zoneName === "battle") {
    actions.push(
      { label: card.tapped ? "Untap" : "Tap", run: () => togglePlaytestTapped("battle", card.uid), tone: "ghost" },
      { label: "Mana Zone", run: () => movePlaytestCard("battle", card.uid, "mana", { faceDown: false, resetTapped: true }) },
      { label: "Graveyard", run: () => movePlaytestCard("battle", card.uid, "graveyard", { faceDown: false, resetTapped: true }) },
      { label: "Hand", run: () => movePlaytestCard("battle", card.uid, "hand", { faceDown: false, resetTapped: true }) }
    );
  }
  if (zoneName === "mana") {
    const civilizations = playtestCardCivilizations(card.card);
    if (!card.tapped) {
      for (const civilization of civilizations.slice(0, Math.max(1, civilizations.length))) {
        actions.push({
          label: `Tap ${civilization}`,
          run: () => togglePlaytestManaTap(card.uid, civilization),
          tone: "ghost"
        });
      }
    } else {
      actions.push(
        { label: "Ready", run: () => togglePlaytestManaTap(card.uid), tone: "ghost" }
      );
    }
    actions.push(
      { label: "Hand", run: () => movePlaytestCard("mana", card.uid, "hand", { faceDown: false, resetTapped: true }) },
      { label: "Battle", run: () => movePlaytestCard("mana", card.uid, "battle", { faceDown: false, resetTapped: true }) },
      { label: "Grave", run: () => movePlaytestCard("mana", card.uid, "graveyard", { faceDown: false, resetTapped: true }) }
    );
  }
  if (zoneName === "graveyard") {
    actions.push(
      { label: "Hand", run: () => movePlaytestCard("graveyard", card.uid, "hand", { faceDown: false, resetTapped: true }) }
    );
  }
  if (zoneName === "shields") {
    actions.push(
      { label: "Break", run: () => movePlaytestCard("shields", card.uid, isShieldTriggerCard(card.card) ? "battle" : "hand", { faceDown: false, resetTapped: true }) },
      { label: "Graveyard", run: () => movePlaytestCard("shields", card.uid, "graveyard", { faceDown: false, resetTapped: true }) }
    );
  }
  return actions;
}

function buildPlaytestCard(zoneName, card) {
  const article = document.createElement("article");
  article.className = "playtest-card";
  article.dataset.zone = zoneName;
  article.dataset.uid = card.uid;
  const canQuickToggleTap = zoneName === "mana" || zoneName === "battle";
  const isEvolutionTarget = zoneName === "battle"
    && state.playtestEvolutionPick
    && state.playtestEvolutionPick.eligibleUids.includes(card.uid);
  let pendingClickTimer = null;
  const toggleSelection = () => {
    if (isEvolutionTarget) {
      completeEvolutionPlay(card.uid);
      return;
    }
    if (state.playtestSelected?.uid === card.uid && state.playtestSelected?.zone === zoneName) {
      state.playtestSelected = null;
    } else {
      state.playtestSelected = { zone: zoneName, uid: card.uid };
    }
    renderPlaytestSandbox();
  };
  const handleCardClick = () => {
    if (!canQuickToggleTap) {
      toggleSelection();
      return;
    }
    window.clearTimeout(pendingClickTimer);
    pendingClickTimer = window.setTimeout(() => {
      pendingClickTimer = null;
      toggleSelection();
    }, 220);
  };
  const handleCardDoubleClick = (event) => {
    if (!canQuickToggleTap) {
      return;
    }
    event.preventDefault();
    window.clearTimeout(pendingClickTimer);
    pendingClickTimer = null;
    togglePlaytestTapped(zoneName, card.uid);
  };
  article.classList.toggle("is-tapped", Boolean(card.tapped));
  article.classList.toggle("is-facedown", Boolean(card.faceDown));
  article.classList.toggle("is-selected", state.playtestSelected?.uid === card.uid && state.playtestSelected?.zone === zoneName);
  article.classList.toggle("is-evolution-target", Boolean(isEvolutionTarget));
  article.classList.toggle("has-underlays", Array.isArray(card.underlays) && card.underlays.length > 0);
  article.addEventListener("click", handleCardClick);
  article.addEventListener("dblclick", handleCardDoubleClick);

  const imageButton = document.createElement("button");
  imageButton.type = "button";
  imageButton.className = "playtest-card-image-button";
  imageButton.setAttribute("aria-label", card.faceDown ? "Hidden shield card" : card.card.name);
  if (card.faceDown) {
    const back = document.createElement("span");
    back.className = "playtest-card-back";
    back.style.background = `linear-gradient(rgba(6, 14, 28, 0.2), rgba(6, 14, 28, 0.6)), url('${playtestCoverImageUrl()}') center / cover no-repeat`;
    const backImage = document.createElement("img");
    backImage.className = "playtest-card-back-image";
    backImage.src = playtestCoverImageUrl();
    backImage.alt = "Card back";
    backImage.loading = "eager";
    backImage.decoding = "async";
    back.append(backImage);
    imageButton.append(back);
  } else {
    const image = document.createElement("img");
    image.className = "playtest-card-image";
    image.src = resolveAssetUrl(card.card.image_path || card.card.illustration_path || DEFAULT_LOGO_URL);
    image.alt = card.card.name;
    image.loading = "lazy";
    image.decoding = "async";
    imageButton.append(image);
  }
  imageButton.addEventListener("click", (event) => {
    event.stopPropagation();
    handleCardClick();
  });
  imageButton.addEventListener("dblclick", (event) => {
    event.stopPropagation();
    handleCardDoubleClick(event);
  });
  article.append(imageButton);
  if (Array.isArray(card.underlays) && card.underlays.length > 0) {
    const badge = document.createElement("span");
    badge.className = "playtest-stack-badge";
    badge.textContent = `+${card.underlays.length}`;
    article.append(badge);
  }
  return article;
}

function renderPlaytestPile() {
  if (!elements.playtestDrawPileZone) {
    return;
  }
  const zone = elements.playtestDrawPileZone;
  zone.replaceChildren();
  const pile = state.playtest.drawPile || [];
  const stack = document.createElement("div");
  stack.className = "playtest-deck-stack";
  stack.setAttribute("role", "button");
  stack.tabIndex = pile.length ? 0 : -1;
  stack.setAttribute("aria-label", pile.length ? "Open library actions" : "Library is empty");
  stack.innerHTML = `
    <div class="playtest-deck-stack-card"></div>
    <div class="playtest-deck-stack-card"></div>
    <div class="playtest-deck-stack-top"></div>
  `;
  for (const layer of stack.querySelectorAll(".playtest-deck-stack-card, .playtest-deck-stack-top")) {
    layer.style.background = `linear-gradient(rgba(6, 14, 28, 0.22), rgba(6, 14, 28, 0.58)), url('${playtestCoverImageUrl()}') center / cover no-repeat`;
    const image = document.createElement("img");
    image.className = "playtest-deck-stack-image";
    image.src = playtestCoverImageUrl();
    image.alt = "Library card back";
    image.loading = "eager";
    image.decoding = "async";
    layer.append(image);
  }
  if (pile.length) {
    stack.addEventListener("click", () => {
      if (state.playtestSelected?.zone === "drawPile") {
        state.playtestSelected = null;
      } else {
        state.playtestSelected = { zone: "drawPile", uid: "library" };
      }
      renderPlaytestSandbox();
    });
    stack.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (state.playtestSelected?.zone === "drawPile") {
          state.playtestSelected = null;
        } else {
          state.playtestSelected = { zone: "drawPile", uid: "library" };
        }
        renderPlaytestSandbox();
      }
    });
  }
  zone.append(stack);
  const meta = document.createElement("div");
  meta.className = "playtest-pile-meta";
  meta.innerHTML = `<strong>${pile.length} cards</strong>`;
  zone.append(meta);
}

function ensurePlaytestActionOverlay() {
  if (elements.playtestActionOverlay || document.querySelector("#playtest-action-overlay")) {
    elements.playtestActionOverlay = document.querySelector("#playtest-action-overlay");
    return;
  }
  const overlay = document.createElement("div");
  overlay.id = "playtest-action-overlay";
  overlay.className = "playtest-action-overlay";
  overlay.hidden = true;
  document.body.append(overlay);
  elements.playtestActionOverlay = overlay;
}

function ensurePlaytestCinematicModal() {
  if (document.querySelector("#playtest-cinematic-modal")) {
    elements.playtestCinematicModal = document.querySelector("#playtest-cinematic-modal");
    elements.playtestCinematicVideo = document.querySelector("#playtest-cinematic-video");
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="playtest-cinematic-modal" class="modal-shell playtest-cinematic-shell" hidden>
      <div class="modal-backdrop playtest-cinematic-backdrop"></div>
      <section class="playtest-cinematic-panel">
        <video id="playtest-cinematic-video" class="playtest-cinematic-video" preload="auto" playsinline></video>
      </section>
    </div>
  `;
  document.body.append(wrapper.firstElementChild);
  elements.playtestCinematicModal = document.querySelector("#playtest-cinematic-modal");
  elements.playtestCinematicVideo = document.querySelector("#playtest-cinematic-video");
}

function renderPlaytestActionOverlay() {
  if (!elements.playtestActionOverlay) {
    return;
  }
  const overlay = elements.playtestActionOverlay;
  overlay.replaceChildren();
  overlay.hidden = true;
  overlay.style.visibility = "hidden";
  if (!state.playtestSelected) {
    return;
  }
  let anchor = null;
  let actions = [];
  if (state.playtestSelected.zone === "drawPile") {
    anchor = elements.playtestDrawPileZone?.querySelector(".playtest-deck-stack");
    actions = [
      { label: "Draw", tone: "default", run: () => drawPlaytestCards(1) },
      { label: "Search", tone: "ghost", run: () => openPlaytestLibrarySearch() }
    ];
  } else {
    const zoneName = state.playtestSelected.zone;
    const card = (state.playtest[zoneName] || []).find((entry) => entry.uid === state.playtestSelected?.uid);
    if (!card) {
      state.playtestSelected = null;
      return;
    }
    anchor = document.querySelector(`.playtest-card[data-zone="${zoneName}"][data-uid="${card.uid}"]`);
    actions = playtestActionDefinitions(zoneName, card);
  }
  if (!anchor || !actions.length) {
    return;
  }
  for (const action of actions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = action.tone === "ghost" ? "small-button ghost-button" : "small-button";
    button.textContent = action.label;
    button.disabled = Boolean(action.disabled);
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      if (action.disabled) {
        return;
      }
      action.run();
    });
    overlay.append(button);
  }
  const rect = anchor.getBoundingClientRect();
  const padding = 12;
  const gap = 10;
  const menuWidth = 168;
  overlay.style.width = `${menuWidth}px`;
  overlay.hidden = false;
  overlay.style.visibility = "hidden";
  overlay.classList.remove("is-below");
  const menuHeight = overlay.offsetHeight || (actions.length * 46) + ((actions.length - 1) * 8);
  let top = rect.top - menuHeight - gap;
  if (top < padding) {
    top = rect.bottom + gap;
  }
  if (top + menuHeight > window.innerHeight - padding) {
    top = Math.max(padding, window.innerHeight - menuHeight - padding);
  }
  let left = rect.left + (rect.width / 2) - (menuWidth / 2);
  if (left < padding) {
    left = padding;
  }
  if (left + menuWidth > window.innerWidth - padding) {
    left = window.innerWidth - menuWidth - padding;
  }
  overlay.style.top = `${Math.round(top)}px`;
  overlay.style.left = `${Math.round(left)}px`;
  overlay.style.visibility = "visible";
  overlay.hidden = false;
}

function renderPlaytestZone(zoneName, container) {
  if (!container) {
    return;
  }
  container.replaceChildren();
  const cards = state.playtest[zoneName] || [];
  if (!cards.length) {
    renderPlaytestZoneEmpty(container, `${zoneLabel(zoneName)} is empty.`);
    return;
  }
  for (const card of cards) {
    container.append(buildPlaytestCard(zoneName, card));
  }
}

function playtestCivilizationColor(civilization) {
  return {
    Light: "#f8df6c",
    Water: "#59c9ff",
    Darkness: "#7f5cff",
    Fire: "#ff7046",
    Nature: "#6be07d"
  }[civilization] || "#d7e8ff";
}

function renderPlaytestManaPool() {
  if (!elements.playtestManaPool) {
    return;
  }
  elements.playtestManaPool.replaceChildren();
  const pool = state.playtest.manaPool || [];
  elements.playtestManaPool.hidden = pool.length === 0;
  for (const entry of pool) {
    const orb = document.createElement("span");
    orb.className = "playtest-mana-orb";
    orb.title = `${entry.civilization} mana`;
    orb.style.setProperty("--mana-orb", playtestCivilizationColor(entry.civilization));
    elements.playtestManaPool.append(orb);
  }
}

function renderPlaytestSandbox() {
  if (!isPlaytestPage) {
    return;
  }
  const hasSource = (state.playtest.sourceCards || []).length > 0;
  if (elements.playtestEmpty) {
    elements.playtestEmpty.hidden = hasSource;
  }
  if (elements.playtestBoard) {
    elements.playtestBoard.hidden = !hasSource;
  }
  if (elements.playtestTurnValue) {
    elements.playtestTurnValue.textContent = String(state.playtest.turn || 1);
  }
  if (elements.playtestTurnInput) {
    elements.playtestTurnInput.value = String(state.playtest.turn || 1);
  }
  if (elements.playtestDrawButton) {
    elements.playtestDrawButton.disabled = !hasSource || state.playtest.drawPile.length === 0;
  }
  if (elements.playtestShuffleButton) {
    elements.playtestShuffleButton.disabled = !hasSource || state.playtest.drawPile.length < 2;
  }
  if (elements.playtestResetButton) {
    elements.playtestResetButton.disabled = !hasSource;
  }
  if (elements.playtestDrawCount) elements.playtestDrawCount.textContent = String(state.playtest.drawPile.length);
  if (elements.playtestShieldCount) elements.playtestShieldCount.textContent = String(state.playtest.shields.length);
  if (elements.playtestHandCount) elements.playtestHandCount.textContent = String(state.playtest.hand.length);
  if (elements.playtestBattleCount) elements.playtestBattleCount.textContent = String(state.playtest.battle.length);
  if (elements.playtestManaCount) elements.playtestManaCount.textContent = String(state.playtest.mana.length);
  if (elements.playtestGraveCount) elements.playtestGraveCount.textContent = String(state.playtest.graveyard.length);
  if (!hasSource) {
    return;
  }
  renderPlaytestPile();
  renderPlaytestZone("shields", elements.playtestShieldsZone);
  renderPlaytestZone("hand", elements.playtestHandZone);
  renderPlaytestZone("battle", elements.playtestBattleZone);
  renderPlaytestZone("mana", elements.playtestManaZone);
  renderPlaytestZone("graveyard", elements.playtestGraveyardZone);
  renderPlaytestManaPool();
  renderPlaytestActionOverlay();
}

async function loadPlaymodeMatches() {
  if (!state.activeProfileId) {
    state.playmodeMatches = [];
    return;
  }
  const payload = await fetchJson(`${API_BASE}/playmode/matches?profile_id=${state.activeProfileId}`);
  state.playmodeMatches = payload.items || [];
}

async function maybeLoadPlaymodeMatchFromQuery() {
  const matchId = new URLSearchParams(window.location.search).get("match");
  if (!matchId || window.location.protocol === "file:") {
    return;
  }
  const suffix = state.activeProfileId ? `?profile_id=${state.activeProfileId}` : "";
  state.playmodeMatch = await fetchJson(`${API_BASE}/playmode/matches/${encodeURIComponent(matchId)}${suffix}`);
}

function renderPlaymodeZoneCards(cards, { hidden = false, count = 0 } = {}) {
  if (hidden) {
    const ghosts = Array.from({ length: Math.min(5, count || 0) }, () => `
      <article class="playmode-mini-card is-facedown">
        <span class="playmode-mini-back" style="background-image:url('${playtestCoverImageUrl()}')"></span>
      </article>
    `).join("");
    return ghosts || `<p class="hero-text playmode-zone-empty">Hidden hand</p>`;
  }
  if (!cards.length) {
    return `<p class="hero-text playmode-zone-empty">Empty</p>`;
  }
  return cards.map((card) => {
    const image = card.face_down
      ? `<span class="playmode-mini-back" style="background-image:url('${playtestCoverImageUrl()}')"></span>`
      : `<img class="playmode-mini-image" src="${escapeHtml(resolveAssetUrl(card.image_path || DEFAULT_LOGO_URL))}" alt="${escapeHtml(card.name)}">`;
    return `
      <article class="playmode-mini-card${card.tapped ? " is-tapped" : ""}${card.face_down ? " is-facedown" : ""}">
        ${image}
      </article>
    `;
  }).join("");
}

function renderPlaymodeSeat(container, player, viewerSeat, adminOverride = false) {
  if (!container || !player) {
    return;
  }
  const isViewer = adminOverride || viewerSeat === player.seat;
  const zones = player.zones || {};
  container.innerHTML = `
    <div class="playmode-seat-header">
      <div>
        <strong>${escapeHtml(player.username ? displayUsername(player.username) : `Player ${player.seat}`)}</strong>
        <span>${escapeHtml(player.deck_title || "No deck selected")}</span>
      </div>
      <span class="chip">${player.ready ? "Ready" : "Waiting"}</span>
    </div>
    <div class="playmode-seat-grid">
      <section class="playmode-zone-card">
        <div class="playmode-zone-head"><span>Shields</span><strong>${zones.shield_count ?? 0}</strong></div>
        <div class="playmode-mini-row">${renderPlaymodeZoneCards(zones.shields || [])}</div>
      </section>
      <section class="playmode-zone-card">
        <div class="playmode-zone-head"><span>Battle Zone</span><strong>${(zones.battle || []).length}</strong></div>
        <div class="playmode-mini-row">${renderPlaymodeZoneCards(zones.battle || [])}</div>
      </section>
      <section class="playmode-zone-card">
        <div class="playmode-zone-head"><span>Mana Zone</span><strong>${(zones.mana || []).length}</strong></div>
        <div class="playmode-mini-row">${renderPlaymodeZoneCards(zones.mana || [])}</div>
      </section>
      <section class="playmode-zone-card">
        <div class="playmode-zone-head"><span>Hand</span><strong>${zones.hand_count ?? 0}</strong></div>
        <div class="playmode-mini-row">${renderPlaymodeZoneCards(zones.hand || [], { hidden: !isViewer, count: zones.hand_count ?? 0 })}</div>
      </section>
      <section class="playmode-zone-card">
        <div class="playmode-zone-head"><span>Deck</span><strong>${zones.deck_count ?? 0}</strong></div>
        <div class="playmode-zone-statline">Library is hidden. Deck order cannot be inspected.</div>
      </section>
      <section class="playmode-zone-card">
        <div class="playmode-zone-head"><span>Graveyard</span><strong>${zones.graveyard_count ?? 0}</strong></div>
        <div class="playmode-mini-row">${renderPlaymodeZoneCards(zones.graveyard || [])}</div>
      </section>
    </div>
  `;
}

function renderPlaymodePage() {
  if (!isPlaymodePage) {
    return;
  }
  const loggedIn = Boolean(state.activeProfileId);
  if (elements.playmodeDenied) {
    elements.playmodeDenied.hidden = loggedIn;
  }
  if (elements.playmodePanel) {
    elements.playmodePanel.hidden = !loggedIn;
  }
  if (!loggedIn) {
    return;
  }
  if (elements.playmodeDeckSelect) {
    const current = elements.playmodeDeckSelect.value;
    elements.playmodeDeckSelect.replaceChildren();
    for (const deck of state.profileDecks || []) {
      const option = document.createElement("option");
      option.value = deck.public_id;
      option.textContent = deck.title;
      elements.playmodeDeckSelect.append(option);
    }
    if (current) {
      elements.playmodeDeckSelect.value = current;
    }
  }
  if (elements.playmodeJoinDeckSelect) {
    const current = elements.playmodeJoinDeckSelect.value;
    elements.playmodeJoinDeckSelect.replaceChildren();
    for (const deck of state.profileDecks || []) {
      const option = document.createElement("option");
      option.value = deck.public_id;
      option.textContent = deck.title;
      elements.playmodeJoinDeckSelect.append(option);
    }
    if (current) {
      elements.playmodeJoinDeckSelect.value = current;
    }
  }
  if (elements.playmodeList) {
    elements.playmodeList.replaceChildren();
    if (!(state.playmodeMatches || []).length) {
      const empty = document.createElement("p");
      empty.className = "hero-text playmode-zone-empty";
      empty.textContent = "No Playmode matches yet. Create one with your own deck.";
      elements.playmodeList.append(empty);
    } else {
      for (const match of state.playmodeMatches) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "builder-surface playmode-match-row";
        button.innerHTML = `
          <strong>${escapeHtml(match.player_one_deck_title || "Deck")} vs ${escapeHtml(match.player_two_deck_title || "Waiting for opponent")}</strong>
          <span>${escapeHtml(match.mode)} • ${escapeHtml(match.status)} • Turn ${match.current_turn}</span>
        `;
        button.addEventListener("click", () => {
          window.location.assign(`${playmodePagePath()}?match=${encodeURIComponent(match.public_id)}`);
        });
        elements.playmodeList.append(button);
      }
    }
  }
  if (elements.playmodeBoardTitle) {
    elements.playmodeBoardTitle.textContent = state.playmodeMatch
      ? `Match ${state.playmodeMatch.public_id}`
      : "No active match loaded";
  }
  if (elements.playmodeBoardMeta) {
    elements.playmodeBoardMeta.textContent = state.playmodeMatch
      ? `${state.playmodeMatch.mode} • ${state.playmodeMatch.status} • Turn ${state.playmodeMatch.current_turn}${state.playmodeMatch.deadline_label ? ` • Deadline ${state.playmodeMatch.deadline_label}` : ""}`
      : "Open a match code or create a new one to see both boards.";
  }
  if (elements.playmodeJoinPanel) {
    const canJoin = Boolean(state.playmodeMatch && !state.playmodeMatch.player_two?.profile_id && state.playmodeMatch.player_one?.profile_id !== state.activeProfileId);
    elements.playmodeJoinPanel.hidden = !canJoin;
  }
  if (elements.playmodeBoard) {
    elements.playmodeBoard.hidden = !state.playmodeMatch;
  }
  if (state.playmodeMatch) {
    renderPlaymodeSeat(elements.playmodePlayerOne, state.playmodeMatch.player_one, state.playmodeMatch.viewer_seat, state.playmodeMatch.admin_override);
    renderPlaymodeSeat(elements.playmodePlayerTwo, state.playmodeMatch.player_two, state.playmodeMatch.viewer_seat, state.playmodeMatch.admin_override);
  }
}

async function createPlaymodeMatch() {
  if (!state.activeProfileId) {
    setStatus("Log in first to create a Playmode match.", "error");
    return;
  }
  const deckPublicId = elements.playmodeDeckSelect?.value;
  const mode = elements.playmodeModeSelect?.value || "live";
  if (!deckPublicId) {
    setStatus("Choose one of your own decks first.", "error");
    return;
  }
  state.playmodeMatch = await fetchJson(`${API_BASE}/playmode/matches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: state.activeProfileId, deck_public_id: deckPublicId, mode })
  });
  await loadPlaymodeMatches();
  renderPlaymodePage();
  setStatus(`Playmode match created. Share code: ${state.playmodeMatch.public_id}`, "success");
}

async function openPlaymodeMatchFromInput() {
  const matchId = elements.playmodeOpenCode?.value.trim();
  if (!matchId) {
    setStatus("Enter a match code first.", "error");
    return;
  }
  if (window.location.protocol === "file:") {
    setStatus("Playmode needs the live web service, not file:// preview.", "error");
    return;
  }
  const suffix = state.activeProfileId ? `?profile_id=${state.activeProfileId}` : "";
  state.playmodeMatch = await fetchJson(`${API_BASE}/playmode/matches/${encodeURIComponent(matchId)}${suffix}`);
  const next = new URL(window.location.href);
  next.searchParams.set("match", matchId);
  window.history.replaceState({}, "", next);
  renderPlaymodePage();
}

async function joinCurrentPlaymodeMatch() {
  if (!state.activeProfileId || !state.playmodeMatch) {
    return;
  }
  const deckPublicId = elements.playmodeJoinDeckSelect?.value;
  if (!deckPublicId) {
    setStatus("Choose one of your own decks before joining.", "error");
    return;
  }
  state.playmodeMatch = await fetchJson(`${API_BASE}/playmode/matches/${encodeURIComponent(state.playmodeMatch.public_id)}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: state.activeProfileId, deck_public_id: deckPublicId })
  });
  await loadPlaymodeMatches();
  renderPlaymodePage();
  setStatus("Joined the match successfully.", "success");
}

async function loadPlaytestSandbox() {
  let payload = null;
  try {
    payload = JSON.parse(window.sessionStorage.getItem(PLAYTEST_STORAGE_KEY) || "null");
  } catch {
    payload = null;
  }
  if (!payload || !(payload.sourceCards || []).length) {
    try {
      payload = JSON.parse(window.localStorage.getItem(PLAYTEST_STORAGE_BACKUP_KEY) || "null");
    } catch {
      payload = null;
    }
  }
  if ((!payload || !(payload.sourceCards || []).length) && window.location.protocol !== "file:") {
    const deckId = new URLSearchParams(window.location.search).get("deck");
    if (deckId) {
      try {
        const deckPayload = await fetchJson(withViewer(`${API_BASE}/decks/${deckId}`));
        payload = emptyPlaytestState(
          deckPayload.title,
          deckPayload.cards.map((entry) => entry.card),
          {
            coverImage: deckPayload.cover_image_url || deriveAutomaticDeckCover(),
            ownerLabel: deckPayload.owner?.username ? displayUsername(deckPayload.owner.username) : "Paladin's Vault"
          }
        );
      } catch {
        payload = null;
      }
    }
  }
  if (payload) {
    applyPlaytestState(payload);
    return;
  }
  applyPlaytestState(emptyPlaytestState());
}

async function loadHistoryPage() {
  if (!state.loadedShareId) {
    const deckId = new URLSearchParams(window.location.search).get("deck");
    if (deckId && window.location.protocol !== "file:") {
      try {
        await loadDeckIntoWorkspace(deckId, { openBuilder: false });
        return;
      } catch {}
    }
  }
  if (state.loadedShareId) {
    try {
      await loadDeckHistory(state.loadedShareId);
    } catch {}
  }
}

async function openPlaytestSandbox() {
  if (totalDeckCards() === 0) {
    setStatus("Build a deck first, then open the playtest sandbox.", "error");
    return;
  }
  await ensureDeckCardsHydratedForPlaytest();
  const sourceCards = buildPlaytestSourceCards();
  if (!sourceCards.length) {
    setStatus("The current deck is missing card data. Search once or reload the deck, then try again.", "error");
    return;
  }
  applyPlaytestState(emptyPlaytestState(deckSnapshotTitle(), sourceCards, {
    coverImage: state.deckCoverImageUrl || deriveAutomaticDeckCover(),
    ownerLabel: displayUsername(activeProfile()?.username || state.loadedDeckOwner?.username || "Paladin's Vault")
  }));
  setupPlaytestGame();
  const target = `${playtestPagePath()}${state.loadedShareId && window.location.protocol !== "file:" ? `?deck=${encodeURIComponent(state.loadedShareId)}` : ""}`;
  window.location.assign(target);
}

async function loadCardDetailPage() {
  const cardId = currentCardDetailId();
  if (!cardId) {
    renderCardDetail(null);
    return;
  }
  if (window.location.protocol === "file:") {
    await loadAllCards();
    const card = state.allCards.find((item) => item.id === cardId) || null;
    renderCardDetail(card);
    return;
  }
  try {
    const card = await fetchJson(`${API_BASE}/cards/${cardId}`);
    renderCardDetail(card);
  } catch {
    renderCardDetail(null);
  }
}

function renderCardDetail(card) {
  if (!isCardDetailPage || !elements.cardDetailLayout || !elements.cardDetailEmpty) {
    return;
  }
  if (!card) {
    document.title = "Paladin's Vault • Card Not Found";
    elements.cardDetailLayout.hidden = true;
    elements.cardDetailEmpty.innerHTML = `<p class="hero-text">This card could not be found. Try returning to the full card browser.</p>`;
    return;
  }

  document.title = `Paladin's Vault • ${card.name}`;
  elements.cardDetailLayout.hidden = false;
  elements.cardDetailEmpty.hidden = true;
  if (elements.cardDetailTitle) {
    elements.cardDetailTitle.textContent = card.name;
  }
  if (elements.cardDetailSubtitle) {
    elements.cardDetailSubtitle.textContent = `${card.type} • ${card.race_label} • ${card.cost} mana`;
  }
  if (elements.cardDetailImage) {
    elements.cardDetailImage.src = card.image_path || card.illustration_path || DEFAULT_LOGO_URL;
    elements.cardDetailImage.alt = card.name;
  }
  if (elements.cardDetailName) {
    elements.cardDetailName.textContent = card.name;
  }
  if (elements.cardDetailCost) {
    elements.cardDetailCost.textContent = `${card.cost}`;
  }
  if (elements.cardDetailCivs) {
    elements.cardDetailCivs.replaceChildren();
    for (const civ of card.civilizations || []) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = civ;
      elements.cardDetailCivs.append(chip);
    }
  }
  if (elements.cardDetailType) {
    elements.cardDetailType.textContent = card.type || "-";
  }
  if (elements.cardDetailRace) {
    elements.cardDetailRace.textContent = card.race_label || "-";
  }
  if (elements.cardDetailPower) {
    elements.cardDetailPower.textContent = card.power || "-";
  }
  if (elements.cardDetailRarity) {
    elements.cardDetailRarity.textContent = card.rarity || "-";
  }
  if (elements.cardDetailText) {
    elements.cardDetailText.textContent = card.text || "No ability text available.";
  }
  if (elements.cardDetailSet) {
    elements.cardDetailSet.textContent = card.set_name || "-";
  }
  if (elements.cardDetailNumber) {
    elements.cardDetailNumber.textContent = card.collector_number || "-";
  }
  if (elements.cardDetailIllustrator) {
    elements.cardDetailIllustrator.textContent = card.illustrator || "-";
  }
  if (elements.cardDetailFlavorWrap && elements.cardDetailFlavor) {
    const hasFlavor = Boolean(card.flavor && card.flavor.trim());
    elements.cardDetailFlavorWrap.hidden = !hasFlavor;
    elements.cardDetailFlavor.textContent = hasFlavor ? card.flavor : "";
  }
}

function ensureMobileNavToggle() {
  const nav = document.querySelector(".top-nav");
  const navLinks = document.querySelector(".top-nav-links");
  const logo = document.querySelector(".menu-logo-link");
  if (!nav || !navLinks || !logo || nav.querySelector("[data-mobile-nav-toggle]")) {
    return;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-hamburger-button";
  button.dataset.mobileNavToggle = "true";
  button.setAttribute("aria-label", "Open navigation menu");
  button.setAttribute("aria-expanded", "false");
  button.innerHTML = '<span></span><span></span><span></span>';
  logo.insertAdjacentElement("afterend", button);
  const sync = () => {
    const open = nav.classList.contains("is-mobile-open");
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
  };
  button.addEventListener("click", () => {
    nav.classList.toggle("is-mobile-open");
    sync();
  });
  for (const link of navLinks.querySelectorAll("a, button, summary")) {
    link.addEventListener("click", () => {
      if (
        window.innerWidth <= 820
        && !link.closest(".nav-avatar-dropdown")
        && !link.closest(".nav-notification-dropdown")
        && !link.closest(".nav-explore-dropdown")
      ) {
        nav.classList.remove("is-mobile-open");
        sync();
      }
    });
  }
  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) {
      nav.classList.remove("is-mobile-open");
      sync();
    }
  });
  for (const trigger of document.querySelectorAll(".nav-avatar-trigger")) {
    if (trigger.dataset.mobileProfileBound === "true") {
      continue;
    }
    trigger.dataset.mobileProfileBound = "true";
    trigger.addEventListener("click", (event) => {
      if (window.innerWidth > 820) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      window.location.assign(window.location.protocol === "file:" ? "./profile.html" : "/profile");
    });
  }
  sync();
}

function scheduleCardSearch(limit = null) {
  if (state.cardSearchDebounce) {
    window.clearTimeout(state.cardSearchDebounce);
  }
  state.cardSearchDebounce = window.setTimeout(async () => {
    await loadCards(limit ?? (isDeckEditorPage ? 60 : 160));
    renderSearchSuggestions();
    renderCards();
  }, 180);
}

function renderSearchSuggestions() {
  if (!elements.searchSuggestions) {
    return;
  }
  const container = elements.searchSuggestions;
  container.replaceChildren();
  const query = (state.filters.search || "").trim();
  if (!isDeckEditorPage || !query) {
    container.hidden = true;
    return;
  }
  const suggestions = state.cards.filter((card) => card?.name).slice(0, 8);
  if (!suggestions.length) {
    container.hidden = true;
    return;
  }
  for (const card of suggestions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-suggestion-item";
    button.innerHTML = `
      <span class="search-suggestion-name">${escapeHtml(card.name)}</span>
      <span class="search-suggestion-meta">${escapeHtml(`${card.cost} mana • ${card.type}`)}</span>
    `;
    button.addEventListener("click", () => {
      state.selectedSearchCardId = card.id;
      state.filters.search = "";
      if (elements.searchInput) {
        elements.searchInput.value = "";
      }
      container.hidden = true;
      state.cards = [];
      renderSelectedSearchCard();
      renderCards();
    });
    container.append(button);
  }
  container.hidden = false;
}

function renderSelectedSearchCard() {
  if (!elements.selectedSearchCard) {
    return;
  }
  const card = state.selectedSearchCardId ? state.cardIndex[String(state.selectedSearchCardId)] : null;
  if (!card) {
    elements.selectedSearchCard.hidden = true;
    elements.selectedSearchCard.replaceChildren();
    return;
  }

  const previewImage = card.image_path || card.illustration_path || "";
  elements.selectedSearchCard.innerHTML = `
    <div class="selected-search-card-art">
      ${previewImage ? `<img src="${escapeHtml(previewImage)}" alt="${escapeHtml(card.name)}" loading="lazy" decoding="async">` : ""}
    </div>
    <div class="selected-search-card-copy">
      <strong>${escapeHtml(card.name)}</strong>
      <span>${escapeHtml(`${card.cost} mana • ${card.type} • ${card.civilizations.join(" / ")}`)}</span>
      <p>${escapeHtml(card.text || "No rules text available.")}</p>
      <div class="selected-search-card-actions">
        <button type="button" class="primary-button" data-selected-add-card>Add to Deck</button>
        <button type="button" class="ghost-button" data-selected-open-card>View Card</button>
      </div>
    </div>
  `;
  elements.selectedSearchCard.hidden = false;
  elements.selectedSearchCard.querySelector("[data-selected-add-card]")?.addEventListener("click", () => addCardToDeck(card.id));
  elements.selectedSearchCard.querySelector("[data-selected-open-card]")?.addEventListener("click", () => openCardDetail(card));
}

function ensureNotificationMenu() {
  const navLinks = document.querySelector(".top-nav-links");
  const avatarMenu = document.querySelector(".nav-avatar-dropdown");
  if (!navLinks || !avatarMenu || document.querySelector("[data-notification-menu]")) {
    return;
  }
  const wrapper = document.createElement("details");
  wrapper.className = "nav-dropdown nav-notification-dropdown";
  wrapper.dataset.notificationMenu = "true";
  wrapper.hidden = true;
  wrapper.innerHTML = `
    <summary class="nav-bell-trigger" aria-label="Open notifications">
      <span class="nav-bell-icon">✦</span>
      <span class="nav-bell-badge" id="nav-bell-badge" hidden>0</span>
    </summary>
    <div class="nav-dropdown-menu notification-dropdown-menu">
      <div class="notification-menu-header">
        <strong>Notifications</strong>
      </div>
      <div id="notification-list" class="notification-list"></div>
    </div>
  `;
  navLinks.insertBefore(wrapper, avatarMenu);
  elements.notificationMenu = wrapper;
  elements.notificationList = wrapper.querySelector("#notification-list");
  elements.notificationBadge = wrapper.querySelector("#nav-bell-badge");
  wrapper.addEventListener("toggle", () => {
    if (wrapper.open) {
      void markNotificationsRead();
    }
  });
  elements.navDropdowns = [...document.querySelectorAll(".nav-dropdown")];
}

function ensureAdminMenuLinks() {
  const loggedInProfile = activeProfile();
  const isAdmin = Boolean(loggedInProfile?.is_admin);
  const navLinks = document.querySelector(".top-nav-links");
  for (const menu of document.querySelectorAll(".profile-dropdown-menu")) {
    const existing = menu.querySelector("[data-admin-menu-link]");
    if (!isAdmin) {
      existing?.remove();
    } else if (!existing) {
      const link = document.createElement("a");
      link.className = "nav-link nav-dropdown-link";
      link.href = "/admin";
      link.dataset.adminMenuLink = "true";
      link.textContent = "Admin";
      menu.insertBefore(link, menu.querySelector(".nav-link-danger") || null);
    }
  }
  if (!navLinks) {
    return;
  }
  const topLevelExisting = navLinks.querySelector("[data-admin-top-link]");
  if (!isAdmin) {
    topLevelExisting?.remove();
    return;
  }
  if (topLevelExisting) {
    return;
  }
  const topLevelLink = document.createElement("a");
  topLevelLink.className = "nav-link";
  topLevelLink.href = "/admin";
  topLevelLink.dataset.adminTopLink = "true";
  topLevelLink.textContent = "Admin";
  const anchorTarget = navLinks.querySelector(".nav-notification-dropdown, .nav-avatar-dropdown, [data-profile-menu]");
  navLinks.insertBefore(topLevelLink, anchorTarget || null);
}

function ensurePlaymodeNavLink() {
  const navLinks = document.querySelector(".top-nav-links");
  if (!navLinks) {
    return;
  }
  const existing = navLinks.querySelector("[data-playmode-top-link]");
  if (existing) {
    existing.href = playmodePagePath();
    return;
  }
  const link = document.createElement("a");
  link.className = "nav-link";
  link.href = playmodePagePath();
  link.dataset.routeLink = "playmode";
  link.dataset.playmodeTopLink = "true";
  link.textContent = "Play Mode";
  const anchorTarget = navLinks.querySelector("[data-login-nav], .nav-notification-dropdown, .nav-avatar-dropdown, [data-profile-menu]");
  navLinks.insertBefore(link, anchorTarget || null);
  elements.routeLinks = [...document.querySelectorAll("[data-route-link]")];
}

async function markNotificationsRead() {
  if (!state.activeProfileId) {
    return;
  }
  const unread = state.notifications.some((item) => !item.read);
  if (!unread) {
    return;
  }
  state.notifications = state.notifications.map((item) => ({ ...item, read: true }));
  renderNotifications();
  try {
    await fetchJson(`${API_BASE}/profiles/${state.activeProfileId}/notifications/read`, {
      method: "POST"
    });
  } catch (error) {
    console.error("Notification read sync failed", error);
    await loadNotifications();
    renderNotifications();
  }
}

function withViewer(url) {
  const next = new URL(url, window.location.origin);
  if (state.activeProfileId) {
    next.searchParams.set("viewer_profile_id", String(state.activeProfileId));
  }
  return `${next.pathname}${next.search}`;
}

function handleBeforeUnload(event) {
  if ((!state.hasUnsavedProfileChanges && !state.autosaveInFlight) || state.deckReadOnly) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
}

function markDeckSaved() {
  state.hasUnsavedProfileChanges = false;
  state.autosaveQueued = false;
  state.pendingChangeNote = null;
  persistDeckSnapshot();
}

function scheduleDeckAutosave() {
  if (!state.activeProfileId || state.deckReadOnly || totalDeckCards() === 0) {
    return;
  }
  void saveDeckToProfile({ silent: true, autosave: true });
}

function markDeckDirty(changeNote = "Updated deck") {
  if (state.deckReadOnly) {
    return;
  }
  state.deckDirtyToken += 1;
  state.hasUnsavedProfileChanges = true;
  state.pendingChangeNote = changeNote;
  persistDeckSnapshot();
  scheduleDeckAutosave();
}

function bindEvents() {
  window.addEventListener("beforeunload", handleBeforeUnload);
  elements.deckTitleInput?.addEventListener("input", () => {
    persistDeckSnapshot();
    markDeckDirty("Updated deck title");
  });
  elements.newDeckButton?.addEventListener("click", startNewDeck);
  elements.openRegisterAvatarPicker?.addEventListener("click", () => openAvatarPicker("register"));
  elements.openProfileAvatarPicker?.addEventListener("click", () => openAvatarPicker("profile"));
  elements.closeAvatarPicker?.addEventListener("click", closeAvatarPickerModal);
  for (const target of elements.closeAvatarModalTargets) {
    target.addEventListener("click", closeAvatarPickerModal);
  }
  elements.closeAuthModal?.addEventListener("click", closeAuthModal);
  for (const target of elements.closeAuthModalTargets) {
    target.addEventListener("click", closeAuthModal);
  }
  elements.closeSignupModal?.addEventListener("click", closeSignupModal);
  for (const target of elements.closeSignupModalTargets) {
    target.addEventListener("click", closeSignupModal);
  }
  elements.closeExploreFiltersButton?.addEventListener("click", closeExploreFiltersModal);
  for (const target of elements.closeExploreFiltersTargets) {
    target.addEventListener("click", closeExploreFiltersModal);
  }
  elements.closeDeckDeleteModal?.addEventListener("click", closeDeckDeleteModal);
  for (const target of elements.closeDeckDeleteTargets) {
    target.addEventListener("click", closeDeckDeleteModal);
  }
  elements.confirmDeckDeleteButton?.addEventListener("click", confirmDeleteDeck);
  elements.openAccountDeleteModalButton?.addEventListener("click", openAccountDeleteModal);
  for (const link of elements.loginNavLinks) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openAuthModal();
    });
  }
  for (const link of elements.signupNavLinks) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openSignupModal();
    });
  }
  for (const button of elements.openAuthModalButtons) {
    button.addEventListener("click", openAuthModal);
  }
  for (const link of elements.routeLinks) {
    if (link.dataset.routeLink !== "builder") continue;
    link.addEventListener("click", (event) => {
      if (state.activeProfileId) {
        return;
      }
      event.preventDefault();
      setStatus("Sign up or log in first to start a new deck.", "error");
      openAuthModal();
    });
  }
  elements.openExploreFiltersButton?.addEventListener("click", openExploreFiltersModal);
  elements.applyExploreFiltersButton?.addEventListener("click", applyExploreFilters);
  elements.resetExploreFiltersButton?.addEventListener("click", resetExploreFilters);
  for (const dropdown of elements.navDropdowns) {
    dropdown.addEventListener("toggle", () => handleNavDropdownToggle(dropdown));
  }
  document.addEventListener("pointerdown", handleDocumentClick, true);
  window.addEventListener("resize", repositionOpenNavDropdowns);
  window.addEventListener("scroll", repositionOpenNavDropdowns, true);
  elements.exportSelect?.addEventListener("change", handleExportSelection);
  elements.openPlaytestButton?.addEventListener("click", () => {
    void openPlaytestSandbox();
  });
  elements.openAdminPlaytestButton?.addEventListener("click", () => {
    void openPlaytestSandbox();
  });
  elements.openPlaymodePageButton?.addEventListener("click", () => {
    window.location.assign(playmodePagePath());
  });
  elements.playmodeCreateButton?.addEventListener("click", () => {
    void createPlaymodeMatch();
  });
  elements.playmodeOpenButton?.addEventListener("click", () => {
    void openPlaymodeMatchFromInput();
  });
  elements.playmodeJoinButton?.addEventListener("click", () => {
    void joinCurrentPlaymodeMatch();
  });
  elements.exploreTypeSelect?.addEventListener("change", handleExploreTypeChange);
  elements.exploreSearchInput?.addEventListener("input", (event) => {
    state.exploreSearch = event.target.value.trim().toLowerCase();
    renderExploreDecks();
    renderExploreUsers();
  });
  elements.builderSortSelect?.addEventListener("change", (event) => {
    state.builderSort = event.target.value;
    persistBuilderPreferences();
    renderBuilder();
  });
  elements.deckVisibilitySelect?.addEventListener("change", (event) => {
    state.deckVisibility = event.target.value === "private" ? "private" : "public";
    persistDeckSnapshot();
    markDeckDirty(`Changed visibility to ${state.deckVisibility === "private" ? "Private" : "Public"}`);
    renderBuilder();
  });
  elements.deckCoverSelect?.addEventListener("change", (event) => {
    state.deckCoverImageUrl = event.target.value || deriveAutomaticDeckCover();
    persistDeckSnapshot();
    markDeckDirty("Changed deck cover");
    renderBuilder();
    renderProfileDecks();
    renderExploreDecks();
  });
  elements.builderViewSelect?.addEventListener("change", (event) => {
    state.builderView = event.target.value === "text" ? "text" : "image";
    persistBuilderPreferences();
    syncBuilderViewControl();
    renderBuilder();
  });
  elements.toggleHistoryButton?.addEventListener("click", () => {
    const target = `${historyPagePath()}${state.loadedShareId && window.location.protocol !== "file:" ? `?deck=${encodeURIComponent(state.loadedShareId)}` : ""}`;
    window.location.assign(target);
  });
  elements.deckWorkspaceTitle?.addEventListener("click", promptRenameDeckTitle);
  elements.deckWorkspaceTitle?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      promptRenameDeckTitle();
    }
  });

  elements.searchInput?.addEventListener("input", (event) => {
    state.filters.search = event.target.value.trim();
    if (state.filters.search) {
      state.selectedSearchCardId = null;
      renderSelectedSearchCard();
    }
    scheduleCardSearch(isDeckEditorPage ? 48 : 120);
  });
  elements.searchInput?.addEventListener("focus", () => {
    renderSearchSuggestions();
  });
  elements.searchInput?.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.searchSuggestions) {
      elements.searchSuggestions.hidden = true;
    }
  });

  elements.civilizationFilter?.addEventListener("change", (event) => {
    state.filters.civilization = event.target.value;
    scheduleCardSearch(isDeckEditorPage ? 48 : 120);
  });

  elements.typeFilter?.addEventListener("change", (event) => {
    state.filters.type = event.target.value;
    scheduleCardSearch(isDeckEditorPage ? 48 : 120);
  });

  elements.costFilter?.addEventListener("input", (event) => {
    state.filters.maxCost = Number(event.target.value);
    elements.costFilterValue.textContent = event.target.value;
    scheduleCardSearch(isDeckEditorPage ? 48 : 120);
  });
  elements.resetFiltersButton?.addEventListener("click", resetDeckEditorFilters);
  elements.playtestSearchInput?.addEventListener("input", () => {
    renderPlaytestSearchResults();
  });
  elements.playtestSearchInput?.addEventListener("focus", () => {
    renderPlaytestSearchResults();
  });
  elements.playtestSearchInput?.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.playtestSearchResults) {
      elements.playtestSearchResults.hidden = true;
    }
  });
  elements.playtestDrawButton?.addEventListener("click", () => drawPlaytestCards(1));
  elements.playtestShuffleButton?.addEventListener("click", () => {
    state.playtest.drawPile = shuffleArray(state.playtest.drawPile);
    persistPlaytestState();
    renderPlaytestSandbox();
  });
  elements.playtestResetButton?.addEventListener("click", () => {
    hardRestartPlaytestGame();
  });
  elements.playtestExitButton?.addEventListener("click", () => {
    const target = `${builderEditorPath()}${state.loadedShareId && window.location.protocol !== "file:" ? `?deck=${encodeURIComponent(state.loadedShareId)}` : ""}`;
    window.location.assign(target);
  });
  elements.playtestTurnInput?.addEventListener("change", (event) => {
    const nextTurn = Math.max(1, Number(event.target.value) || 1);
    state.playtest.turn = nextTurn;
    persistPlaytestState();
    renderPlaytestSandbox();
  });
  elements.playtestTurnInput?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    const nextTurn = Math.max(1, Number(event.target.value) || 1);
    state.playtest.turn = nextTurn;
    persistPlaytestState();
    renderPlaytestSandbox();
  });
  elements.playtestTurnInc?.addEventListener("click", () => {
    advancePlaytestTurn();
  });

  elements.printDeckSelect?.addEventListener("change", async (event) => {
    await loadPrintDeckSelection(event.target.value);
  });

  elements.clearDeckButton?.addEventListener("click", () => {
    if (state.deckReadOnly) {
      setStatus("This deck is read-only. Duplicate it to your profile to edit it.", "error");
      return;
    }
    state.deck = {};
    state.loadedShareId = null;
    resetDeckExportLinks();
    persistDeckSnapshot();
    markDeckDirty("Cleared deck");
    setStatus("", "info");
    renderBuilder();
    renderPrintPages();
    renderHeaderStats();
  });

  elements.saveDeckButton?.addEventListener("click", saveDeckToProfile);
  elements.importDeckInput?.addEventListener("change", importDeckJson);
  elements.generatePrintButton?.addEventListener("click", renderPrintPages);
  elements.windowPrintButton?.addEventListener("click", () => window.print());
  elements.createProfileButton?.addEventListener("click", createProfile);
  elements.saveProfileUsernameButton?.addEventListener("click", saveProfileUsername);
  elements.saveProfileAvatarButton?.addEventListener("click", saveProfileAvatar);
  elements.loginButton?.addEventListener("click", loginProfile);
  for (const field of [elements.loginEmail, elements.loginPassword]) {
    field?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        void loginProfile();
      }
    });
  }
  for (const field of [elements.newProfileName, elements.registerEmail, elements.registerPassword]) {
    field?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        void createProfile();
      }
    });
  }
  elements.resendVerificationButton?.addEventListener("click", resendVerificationEmail);
  elements.logoutButton?.addEventListener("click", logoutProfile);
  elements.followProfileButton?.addEventListener("click", toggleFollowViewedProfile);
  for (const link of elements.logoutNavLinks) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      logoutProfile();
    });
  }
  elements.textImportButton?.addEventListener("click", importTextDeck);
  elements.adminNotifyButton?.addEventListener("click", sendAdminNotification);
  elements.adminEmailButton?.addEventListener("click", sendAdminEmail);
  elements.contactSubmitButton?.addEventListener("click", submitContactMessage);
  elements.welcomePrimaryLink?.addEventListener("click", (event) => {
    if (state.activeProfileId) {
      return;
    }
    event.preventDefault();
    setStatus("Sign up or log in first to start a new deck.", "error");
    openAuthModal();
  });
}

function setActiveNav() {
  for (const link of elements.routeLinks) {
    const route = link.dataset.routeLink;
    const isExplore = route === "explore" && (page === "explore-decks" || page === "cards");
    const isBuilder = route === "builder" && (isBuilderLandingPage || isDeckEditorPage);
    link.classList.toggle("is-active", isExplore || isBuilder || route === page);
  }
}

function hydrateBuilderPreferences() {
  try {
    const raw = window.localStorage.getItem(BUILDER_PREFS_KEY);
    if (!raw) {
      if (elements.builderSortSelect) elements.builderSortSelect.value = state.builderSort;
      syncBuilderViewControl();
      return;
    }
    const payload = JSON.parse(raw);
    if (payload.view === "image" || payload.view === "text") {
      state.builderView = payload.view;
    }
    if (payload.sort === "mana" || payload.sort === "civilization") {
      state.builderSort = payload.sort;
    }
  } catch {}
  syncBuilderViewControl();
  if (elements.builderSortSelect) {
    elements.builderSortSelect.value = state.builderSort;
  }
}

function persistBuilderPreferences() {
  window.localStorage.setItem(BUILDER_PREFS_KEY, JSON.stringify({
    view: state.builderView,
    sort: state.builderSort
  }));
}

function syncBuilderViewControl() {
  if (elements.builderViewSelect) {
    elements.builderViewSelect.value = state.builderView === "text" ? "text" : "image";
  }
}

function resetDeckEditorFilters() {
  state.filters.search = "";
  state.selectedSearchCardId = null;
  state.filters.civilization = "all";
  state.filters.type = "all";
  state.filters.maxCost = state.filterDefaults.maxCost;
  if (elements.searchInput) elements.searchInput.value = "";
  if (elements.civilizationFilter) elements.civilizationFilter.value = "all";
  if (elements.typeFilter) elements.typeFilter.value = "all";
  if (elements.costFilter) elements.costFilter.value = String(state.filterDefaults.maxCost);
  if (elements.costFilterValue) elements.costFilterValue.textContent = String(state.filterDefaults.maxCost);
  scheduleCardSearch(isDeckEditorPage ? 48 : 120);
}

function promptRenameDeckTitle() {
  if (state.deckReadOnly || !elements.deckTitleInput) {
    return;
  }
  const currentTitle = deckSnapshotTitle();
  const nextTitle = window.prompt("Rename deck", currentTitle);
  if (nextTitle === null) {
    return;
  }
  const trimmed = nextTitle.trim();
  if (!trimmed || trimmed === currentTitle) {
    return;
  }
  elements.deckTitleInput.value = trimmed;
  persistDeckSnapshot();
  markDeckDirty("Updated deck title");
  renderBuilder();
}

async function hydrateProfiles() {
  const storedId = Number(window.localStorage.getItem(PROFILE_STORAGE_KEY));
  const params = new URLSearchParams();
  if (storedId) {
    params.set("viewer_profile_id", String(storedId));
  }
  const payload = await fetchJson(`${API_BASE}/profiles${params.toString() ? `?${params.toString()}` : ""}`);
  state.profiles = payload.items;
  state.activeProfileId = state.profiles.some((profile) => profile.id === storedId) ? storedId : null;
  persistActiveProfileCache();
}

async function hydrateDeckCards() {
  const ids = Object.keys(state.deck);
  if (ids.length === 0) {
    return;
  }
  const payload = await fetchJson(`${API_BASE}/cards/by-ids?ids=${ids.join(",")}`);
  for (const card of payload.items) {
    state.cardIndex[String(card.id)] = card;
  }
}

async function hydrateFilters() {
  if (!elements.civilizationFilter || !elements.typeFilter) {
    return;
  }

  const metadata = await fetchJson(`${API_BASE}/metadata`);
  fillSelect(elements.civilizationFilter, metadata.civilizations);
  fillSelect(elements.typeFilter, metadata.types);
  elements.costFilter.max = String(metadata.max_cost ?? 14);
  state.filterDefaults.maxCost = metadata.max_cost ?? 14;
  state.filters.maxCost = state.filterDefaults.maxCost;
  elements.costFilter.value = String(state.filters.maxCost);
  elements.costFilterValue.textContent = String(state.filters.maxCost);
}

function fillSelect(select, values) {
  if (!select || select.dataset.hydrated === "true") {
    return;
  }
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
  select.dataset.hydrated = "true";
}

async function loadCards(limit = 160) {
  const params = new URLSearchParams();
  if (state.filters.search) params.set("search", state.filters.search);
  if (state.filters.civilization !== "all") params.set("civilization", state.filters.civilization);
  if (state.filters.type !== "all") params.set("type", state.filters.type);
  params.set("max_cost", String(state.filters.maxCost));
  params.set("limit", String(limit));

  const requestId = ++state.cardsRequestId;
  const payload = await fetchJson(`${API_BASE}/cards?${params.toString()}`);
  if (requestId !== state.cardsRequestId) {
    return;
  }
  state.cards = payload.items;
  for (const card of payload.items) {
    state.cardIndex[String(card.id)] = card;
  }
  state.cardsLoaded = true;
}

async function loadAllCards() {
  if (state.allCards.length > 0) {
    return;
  }
  const payload = await fetchJson(`${API_BASE}/cards?limit=5000&max_cost=99`);
  state.allCards = payload.items;
  for (const card of payload.items) {
    state.cardIndex[String(card.id)] = card;
  }
}

async function loadProfileDecks(profileId) {
  if (!profileId) {
    state.profileDecks = [];
    state.likedDecks = [];
    state.activeProfileDetail = null;
    renderBuilderDeckOptions();
    renderBuilderEntry();
    renderPrintDeckOptions();
    return;
  }
  const payload = await fetchJson(withViewer(`${API_BASE}/profiles/${profileId}`));
  state.activeProfileDetail = payload;
  state.profileDecks = payload.decks;
  state.likedDecks = payload.liked_decks || [];
  renderBuilderDeckOptions();
  renderBuilderEntry();
  renderPrintDeckOptions();
  renderProfileDecks();
}

async function loadExploreDecks() {
  const payload = await fetchJson(withViewer(`${API_BASE}/decks`));
  state.exploreDecks = payload.items;
}

async function loadNotifications() {
  if (!state.activeProfileId) {
    state.notifications = [];
    return;
  }
  const payload = await fetchJson(`${API_BASE}/profiles/${state.activeProfileId}/notifications`);
  state.notifications = payload.items || [];
}

async function loadAdminOverview() {
  if (!state.activeProfileId || !activeProfile()?.is_admin) {
    state.adminOverview = null;
    return;
  }
  try {
    state.adminOverview = await fetchJson(`${API_BASE}/admin/overview?admin_profile_id=${state.activeProfileId}`);
  } catch (error) {
    state.adminOverview = null;
    setStatus(error.message || "Admin overview could not be loaded.", "error");
  }
}

async function maybeLoadViewedProfile() {
  const params = new URLSearchParams(window.location.search);
  const username = params.get("user");
  if (!username) {
    state.viewedProfile = null;
    return;
  }
  try {
    state.viewedProfile = await fetchJson(withViewer(`${API_BASE}/profiles/by-username/${encodeURIComponent(username)}`));
    if (state.viewedProfile?.is_admin && state.viewedProfile.id !== state.activeProfileId) {
      state.viewedProfile = null;
    }
  } catch {
    state.viewedProfile = null;
  }
}

function syncDeckSummaryAcrossState(updatedDeck) {
  const replaceIn = (items) => items.map((deck) => deck.public_id === updatedDeck.public_id ? { ...deck, ...updatedDeck } : deck);
  state.profileDecks = replaceIn(state.profileDecks);
  state.likedDecks = replaceIn(state.likedDecks);
  state.exploreDecks = replaceIn(state.exploreDecks);
  if (state.activeProfileDetail?.decks) {
    state.activeProfileDetail.decks = replaceIn(state.activeProfileDetail.decks);
  }
  if (state.activeProfileDetail?.liked_decks) {
    state.activeProfileDetail.liked_decks = replaceIn(state.activeProfileDetail.liked_decks);
  }
  if (state.viewedProfile?.decks) {
    state.viewedProfile.decks = replaceIn(state.viewedProfile.decks);
  }
  if (state.viewedProfile?.liked_decks) {
    state.viewedProfile.liked_decks = replaceIn(state.viewedProfile.liked_decks);
  }
  if (state.loadedShareId === updatedDeck.public_id) {
    state.loadedDeckLikeCount = updatedDeck.like_count || 0;
    state.loadedDeckLikedByViewer = Boolean(updatedDeck.liked_by_viewer);
  }
}

async function toggleDeckLike(publicId) {
  if (!state.activeProfileId) {
    setStatus("Log in first to like decks.", "error");
    openAuthModal();
    return;
  }
  let updated;
  try {
    updated = await fetchJson(`${API_BASE}/decks/${publicId}/like`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: state.activeProfileId })
    });
  } catch (error) {
    setStatus(error.message || "Like update failed.", "error");
    return;
  }
  syncDeckSummaryAcrossState(updated);
  if (state.activeProfileId) {
    await loadProfileDecks(state.activeProfileId);
    await loadNotifications();
  }
  if (page === "profile" && state.viewedProfile?.username) {
    await maybeLoadViewedProfile();
  }
  if (needsExploreDecks(page)) {
    await loadExploreDecks();
  }
  renderProfileDecks();
  renderExploreDecks();
  renderNotifications();
  setStatus(updated.liked_by_viewer ? `Liked ${updated.title}` : `Removed like from ${updated.title}`, "success");
}

function maybeLoadLocalDeck() {
  try {
    const raw = window.localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) return;
    const payload = JSON.parse(raw);
    state.deck = payload.deck ?? {};
    state.loadedShareId = payload.shareId ?? null;
    state.deckVisibility = payload.visibility === "private" ? "private" : "public";
    state.deckCoverImageUrl = payload.coverImageUrl ?? null;
    state.hasUnsavedProfileChanges = Boolean(payload.dirty);
    if (elements.deckTitleInput && payload.title) {
      elements.deckTitleInput.value = payload.title;
    }
  if (elements.deckVisibilitySelect) {
    elements.deckVisibilitySelect.value = state.deckVisibility;
  }
  if (elements.pdfExportLink && state.loadedShareId) {
    elements.pdfExportLink.href = withViewer(`${API_BASE}/decks/${state.loadedShareId}/pdf`);
  }
  if (elements.printPdfExportLink && state.loadedShareId) {
    elements.printPdfExportLink.href = withViewer(`${API_BASE}/decks/${state.loadedShareId}/pdf`);
  }
  if (state.hasUnsavedProfileChanges) {
    scheduleDeckAutosave();
  } else {
    markDeckSaved();
  }
  } catch {
    setStatus("Local deck data could not be loaded.");
  }
}

async function maybeLoadSharedDeck() {
  const shareMatch = window.location.pathname.match(/^\/share\/([a-z0-9-]+)$/i);
  if (!shareMatch) return;

  const payload = await loadDeckIntoWorkspace(shareMatch[1], { openBuilder: true });
  setStatus(`Loaded shared deck: ${payload.title}${payload.owner ? ` by ${displayUsername(payload.owner.username)}` : ""}`, "success");
}

function renderContactPage() {
  if (!elements.contactUsername || !elements.contactEmail) {
    return;
  }
  const profile = activeProfile();
  if (profile) {
    elements.contactUsername.value = displayUsername(profile.username);
    elements.contactEmail.value = profile.email || "";
  }
}

async function submitContactMessage() {
  const profile = activeProfile();
  const username = elements.contactUsername?.value.trim() || profile?.username || "";
  const email = elements.contactEmail?.value.trim() || profile?.email || "";
  const subject = elements.contactSubject?.value.trim() || "";
  const message = elements.contactMessage?.value.trim() || "";
  if (!username || !email || !subject || !message) {
    setStatus("Enter username, email, subject, and message first.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/contact-messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profile?.id || null,
        username,
        email,
        subject,
        message
      })
    });
    if (elements.contactSubject) elements.contactSubject.value = "";
    if (elements.contactMessage) elements.contactMessage.value = "";
    setStatus(payload.message || "Message sent.", "success");
    if (page === "admin" && state.activeProfileId && activeProfile()?.is_admin) {
      await loadAdminOverview();
      renderAdminPage();
    }
  } catch (error) {
    setStatus(error.message || "Contact message could not be sent.", "error");
  }
}

function renderWelcome() {
  if (!elements.welcomeMessage || !elements.welcomePrimaryLink) {
    return;
  }

  const profile = activeProfile();
  if (profile) {
    elements.welcomeMessage.textContent = `Welcome ${profile.display_name}!`;
    elements.welcomePrimaryLink.href = "/builder";
  } else {
    elements.welcomeMessage.textContent = "Build a new deck or browse what the community has already saved.";
    elements.welcomePrimaryLink.href = "#";
  }
}

function handleExploreTypeChange(event) {
  const value = event.target.value;
  if (value === "cards") {
    window.location.href = "/cards";
    return;
  }
  const next = new URL("/explore-decks", window.location.origin);
  next.searchParams.set("type", value);
  window.location.href = next.pathname + next.search;
}

function renderExploreSections() {
  if (!elements.exploreTypeSelect) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const value = params.get("type") || "decks";
  elements.exploreTypeSelect.value = value;
  if (elements.exploreSearchInput) {
    elements.exploreSearchInput.placeholder = value === "users"
      ? "Filter users by username"
      : "Filter decks by title or owner";
  }
  if (elements.exploreDecksPanel) {
    elements.exploreDecksPanel.hidden = value !== "decks";
  }
  if (elements.exploreUsersPanel) {
    elements.exploreUsersPanel.hidden = value !== "users";
  }
}

function renderAuthNavigation() {
  const loggedIn = Boolean(activeProfile());
  for (const link of elements.loginNavLinks) {
    link.hidden = loggedIn;
    link.style.display = loggedIn ? "none" : "";
  }
  for (const link of elements.signupNavLinks) {
    link.hidden = loggedIn;
    link.style.display = loggedIn ? "none" : "";
  }
  for (const menu of elements.profileMenus) {
    menu.hidden = !loggedIn;
    menu.style.display = !loggedIn ? "none" : "";
  }
  for (const link of elements.myDecksLinks) {
    link.hidden = !loggedIn;
  }
  for (const link of elements.logoutNavLinks) {
    link.hidden = !loggedIn;
  }
  for (const link of elements.routeLinks) {
    if (link.dataset.routeLink !== "builder") continue;
    link.href = loggedIn ? "/builder" : "#";
  }
  if (elements.welcomePrimaryLink) {
    elements.welcomePrimaryLink.href = loggedIn ? "/builder" : "#";
  }
  if (elements.notificationMenu) {
    elements.notificationMenu.hidden = !loggedIn;
  }
  for (const avatar of elements.navAvatars) {
    if (!loggedIn) {
      avatar.textContent = "PV";
      setAvatarArt(avatar, DEFAULT_LOGO_URL);
      avatar.classList.add("profile-avatar-image");
      continue;
    }
    const profile = activeProfile();
    if (profile?.avatar_url) {
      avatar.textContent = "";
      setAvatarArt(avatar, profile.avatar_url);
    } else {
      avatar.textContent = initials(profile?.display_name || profile?.username || "Paladin's Vault");
      setAvatarArt(avatar, DEFAULT_LOGO_URL);
    }
    avatar.classList.add("profile-avatar-image");
  }
  ensurePlaymodeNavLink();
  ensureAdminMenuLinks();
  renderTestPlayAccess();
}

function renderTestPlayAccess() {
  const isAdmin = Boolean(activeProfile()?.is_admin);
  for (const panel of elements.deckTestingPanels || []) {
    panel.hidden = false;
  }
  if (elements.openAdminPlaytestButton) {
    elements.openAdminPlaytestButton.hidden = !isAdmin;
  }
}

function ensureExportModal() {
  if (document.querySelector("#export-progress-modal")) {
    elements.exportProgressModal = document.querySelector("#export-progress-modal");
    elements.exportProgressClose = document.querySelector("#close-export-progress-modal");
    elements.exportProgressCloseTargets = [...document.querySelectorAll("[data-close-export-progress-modal]")];
    elements.exportProgressTitle = document.querySelector("#export-progress-title");
    elements.exportProgressMessage = document.querySelector("#export-progress-message");
    elements.exportProgressBar = document.querySelector("#export-progress-bar");
    elements.exportProgressPercent = document.querySelector("#export-progress-percent");
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="export-progress-modal" class="modal-shell" hidden>
      <div class="modal-backdrop" data-close-export-progress-modal></div>
      <section class="panel modal-panel auth-modal-panel export-progress-modal-panel">
        <div class="panel-header">
          <div>
            <p class="section-label">Export</p>
            <h2 id="export-progress-title">Preparing export</h2>
          </div>
          <button id="close-export-progress-modal" type="button" class="ghost-button">Close</button>
        </div>
        <p id="export-progress-message" class="hero-text">Please wait while Paladin's Vault prepares your file.</p>
        <div class="export-progress-track">
          <div id="export-progress-bar" class="export-progress-bar"></div>
        </div>
        <p id="export-progress-percent" class="export-progress-percent">0%</p>
      </section>
    </div>
  `;
  document.body.append(wrapper.firstElementChild);
  elements.exportProgressModal = document.querySelector("#export-progress-modal");
  elements.exportProgressClose = document.querySelector("#close-export-progress-modal");
  elements.exportProgressCloseTargets = [...document.querySelectorAll("[data-close-export-progress-modal]")];
  elements.exportProgressTitle = document.querySelector("#export-progress-title");
  elements.exportProgressMessage = document.querySelector("#export-progress-message");
  elements.exportProgressBar = document.querySelector("#export-progress-bar");
  elements.exportProgressPercent = document.querySelector("#export-progress-percent");
  elements.exportProgressClose?.addEventListener("click", closeExportModal);
  for (const target of elements.exportProgressCloseTargets) {
    target.addEventListener("click", closeExportModal);
  }
}

function setBootLoadingState(isLoading) {
  document.body.classList.toggle("app-boot-loading", isLoading);
}

function openExportModal(title, message, percent = 0) {
  ensureExportModal();
  if (elements.exportProgressTitle) elements.exportProgressTitle.textContent = title;
  if (elements.exportProgressMessage) elements.exportProgressMessage.textContent = message;
  if (elements.exportProgressBar) elements.exportProgressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  if (elements.exportProgressPercent) elements.exportProgressPercent.textContent = `${Math.round(percent)}%`;
  if (elements.exportProgressModal) elements.exportProgressModal.hidden = false;
}

function updateExportModal(message, percent) {
  if (elements.exportProgressMessage) elements.exportProgressMessage.textContent = message;
  if (elements.exportProgressBar) elements.exportProgressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  if (elements.exportProgressPercent) elements.exportProgressPercent.textContent = `${Math.round(percent)}%`;
}

async function fetchBlobWithProgress(url, options = {}) {
  const {
    startPercent = 0,
    endPercent = 95,
    progressMessage = "Downloading export..."
  } = options;
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) {
    let detail = "";
    try {
      detail = await response.text();
    } catch {
      detail = "";
    }
    throw new Error(detail || `Export request failed: ${response.status}`);
  }

  if (!response.body) {
    updateExportModal(progressMessage, endPercent);
    return await response.blob();
  }

  const total = Number(response.headers.get("Content-Length") || 0);
  const reader = response.body.getReader();
  const chunks = [];
  let received = 0;
  let tick = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    if (value) {
      chunks.push(value);
      received += value.byteLength;
    }
    tick += 1;
    const percent = total > 0
      ? startPercent + (received / total) * (endPercent - startPercent)
      : Math.min(endPercent, startPercent + tick * 6);
    updateExportModal(progressMessage, percent);
  }

  updateExportModal(progressMessage, endPercent);
  return new Blob(chunks, {
    type: response.headers.get("Content-Type") || "application/octet-stream"
  });
}

function completeExportModal(message) {
  if (elements.exportProgressTitle) elements.exportProgressTitle.textContent = "Export complete";
  updateExportModal(message, 100);
}

function failExportModal(message) {
  if (elements.exportProgressTitle) elements.exportProgressTitle.textContent = "Export failed";
  updateExportModal(message, 100);
}

function closeExportModal() {
  if (elements.exportProgressModal) {
    elements.exportProgressModal.hidden = true;
  }
}

function ensureAdminMonthModal() {
  if (document.querySelector("#admin-month-modal")) {
    elements.adminMonthModal = document.querySelector("#admin-month-modal");
    elements.adminMonthModalTitle = document.querySelector("#admin-month-modal-title");
    elements.adminMonthModalLabel = document.querySelector("#admin-month-modal-label");
    elements.adminMonthProfilesList = document.querySelector("#admin-month-profiles-list");
    elements.adminMonthDecksList = document.querySelector("#admin-month-decks-list");
    elements.closeAdminMonthModal = document.querySelector("#close-admin-month-modal");
    elements.closeAdminMonthModalTargets = [...document.querySelectorAll("[data-close-admin-month-modal]")];
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="admin-month-modal" class="modal-shell" hidden>
      <div class="modal-backdrop" data-close-admin-month-modal></div>
      <section class="panel modal-panel admin-month-modal-panel">
        <div class="panel-header">
          <div>
            <p class="section-label">Monthly Drilldown</p>
            <h2 id="admin-month-modal-title">Monthly activity</h2>
            <p id="admin-month-modal-label" class="hero-text">Explore the users and decks created during this month.</p>
          </div>
          <button id="close-admin-month-modal" type="button" class="ghost-button">Close</button>
        </div>
        <div class="admin-month-modal-grid">
          <section class="summary-card">
            <p class="section-label">Users</p>
            <h3>Joined this month</h3>
            <div id="admin-month-profiles-list" class="admin-month-detail-list"></div>
          </section>
          <section class="summary-card">
            <p class="section-label">Decks</p>
            <h3>Created this month</h3>
            <div id="admin-month-decks-list" class="admin-month-detail-list"></div>
          </section>
        </div>
      </section>
    </div>
  `;
  document.body.append(wrapper.firstElementChild);
  elements.adminMonthModal = document.querySelector("#admin-month-modal");
  elements.adminMonthModalTitle = document.querySelector("#admin-month-modal-title");
  elements.adminMonthModalLabel = document.querySelector("#admin-month-modal-label");
  elements.adminMonthProfilesList = document.querySelector("#admin-month-profiles-list");
  elements.adminMonthDecksList = document.querySelector("#admin-month-decks-list");
  elements.closeAdminMonthModal = document.querySelector("#close-admin-month-modal");
  elements.closeAdminMonthModalTargets = [...document.querySelectorAll("[data-close-admin-month-modal]")];
  elements.closeAdminMonthModal?.addEventListener("click", closeAdminMonthModal);
  for (const target of elements.closeAdminMonthModalTargets) {
    target.addEventListener("click", closeAdminMonthModal);
  }
}

function ensurePlaytestLibraryModal() {
  if (document.querySelector("#playtest-library-modal")) {
    elements.playtestLibraryModal = document.querySelector("#playtest-library-modal");
    elements.playtestLibrarySearchInput = document.querySelector("#playtest-library-search-input");
    elements.playtestLibrarySearchResults = document.querySelector("#playtest-library-search-results");
    elements.closePlaytestLibraryModal = document.querySelector("#close-playtest-library-modal");
    elements.closePlaytestLibraryModalTargets = [...document.querySelectorAll("[data-close-playtest-library-modal]")];
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="playtest-library-modal" class="modal-shell" hidden>
      <div class="modal-backdrop" data-close-playtest-library-modal></div>
      <section class="panel modal-panel auth-modal-panel">
        <div class="panel-header">
          <div>
            <p class="section-label">Library Search</p>
            <h2>Take a card from the deck</h2>
          </div>
          <button id="close-playtest-library-modal" type="button" class="ghost-button">Close</button>
        </div>
        <label class="field">
          <span>Search Library</span>
          <input id="playtest-library-search-input" type="text" placeholder="Search a card name">
        </label>
        <div id="playtest-library-search-results" class="playtest-search-results playtest-search-results-static"></div>
      </section>
    </div>
  `;
  document.body.append(wrapper.firstElementChild);
  elements.playtestLibraryModal = document.querySelector("#playtest-library-modal");
  elements.playtestLibrarySearchInput = document.querySelector("#playtest-library-search-input");
  elements.playtestLibrarySearchResults = document.querySelector("#playtest-library-search-results");
  elements.closePlaytestLibraryModal = document.querySelector("#close-playtest-library-modal");
  elements.closePlaytestLibraryModalTargets = [...document.querySelectorAll("[data-close-playtest-library-modal]")];
  elements.closePlaytestLibraryModal?.addEventListener("click", closePlaytestLibraryModal);
  for (const target of elements.closePlaytestLibraryModalTargets) {
    target.addEventListener("click", closePlaytestLibraryModal);
  }
  elements.playtestLibrarySearchInput?.addEventListener("input", renderPlaytestLibrarySearchResults);
  elements.playtestLibrarySearchInput?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePlaytestLibraryModal();
    }
  });
}

function closeAdminMonthModal() {
  if (elements.adminMonthModal) {
    elements.adminMonthModal.hidden = true;
  }
}

async function openAdminMonthModal(label) {
  if (!state.activeProfileId || !activeProfile()?.is_admin) {
    return;
  }
  ensureAdminMonthModal();
  if (!elements.adminMonthModal) {
    return;
  }
  elements.adminMonthModal.hidden = false;
  if (elements.adminMonthModalTitle) {
    elements.adminMonthModalTitle.textContent = `Monthly activity for ${label}`;
  }
  if (elements.adminMonthModalLabel) {
    elements.adminMonthModalLabel.textContent = "Loading users and decks for this month...";
  }
  if (elements.adminMonthProfilesList) {
    elements.adminMonthProfilesList.innerHTML = '<p class="hero-text">Loading users...</p>';
  }
  if (elements.adminMonthDecksList) {
    elements.adminMonthDecksList.innerHTML = '<p class="hero-text">Loading decks...</p>';
  }
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/admin/month-details?admin_profile_id=${state.activeProfileId}&month=${encodeURIComponent(label)}`);
  } catch (error) {
    if (elements.adminMonthModalLabel) {
      elements.adminMonthModalLabel.textContent = error.message || "Monthly activity could not be loaded.";
    }
    if (elements.adminMonthProfilesList) {
      elements.adminMonthProfilesList.innerHTML = '<p class="hero-text">No user details available.</p>';
    }
    if (elements.adminMonthDecksList) {
      elements.adminMonthDecksList.innerHTML = '<p class="hero-text">No deck details available.</p>';
    }
    return;
  }
  if (elements.adminMonthModalLabel) {
    elements.adminMonthModalLabel.textContent = `${payload.profiles.length} users joined and ${payload.decks.length} decks were created in ${payload.label}.`;
  }
  if (elements.adminMonthProfilesList) {
    elements.adminMonthProfilesList.replaceChildren();
    if (!payload.profiles.length) {
      const empty = document.createElement("p");
      empty.className = "hero-text";
      empty.textContent = "No users joined in this month.";
      elements.adminMonthProfilesList.append(empty);
    } else {
      for (const profile of payload.profiles) {
        const item = document.createElement("article");
        item.className = "admin-month-detail-card";
        item.innerHTML = `
          <strong>${escapeHtml(displayUsername(profile.username))}</strong>
          <span>${escapeHtml(profile.email || "No email")}</span>
          <small>${profile.email_verified ? "Verified" : "Unverified"} • ${escapeHtml(profile.created_at_label)}</small>
        `;
        elements.adminMonthProfilesList.append(item);
      }
    }
  }
  if (elements.adminMonthDecksList) {
    elements.adminMonthDecksList.replaceChildren();
    if (!payload.decks.length) {
      const empty = document.createElement("p");
      empty.className = "hero-text";
      empty.textContent = "No decks were created in this month.";
      elements.adminMonthDecksList.append(empty);
    } else {
      for (const deck of payload.decks) {
        const item = document.createElement("article");
        item.className = "admin-month-detail-card";
        item.innerHTML = `
          <strong>${escapeHtml(deck.title)}</strong>
          <span>${deck.card_total} cards • ${escapeHtml(deck.visibility)}</span>
          <small>${deck.owner_username ? `by ${escapeHtml(displayUsername(deck.owner_username))} • ` : ""}${escapeHtml(deck.created_at_label)}</small>
        `;
        elements.adminMonthDecksList.append(item);
      }
    }
  }
}

function renderNotifications() {
  if (!elements.notificationList) {
    return;
  }
  elements.notificationList.replaceChildren();
  const unread = state.notifications.filter((item) => !item.read).length;
  if (elements.notificationBadge) {
    elements.notificationBadge.hidden = unread === 0;
    elements.notificationBadge.textContent = String(unread);
  }
  if (state.notifications.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "No notifications yet.";
    elements.notificationList.append(empty);
    return;
  }
  for (const item of state.notifications) {
    const row = document.createElement("a");
    row.className = "notification-item";
    row.href = item.deck_public_id ? `/share/${item.deck_public_id}` : (item.actor ? `/profile?user=${encodeURIComponent(item.actor.username)}` : "/profile");
    const actor = item.actor ? displayUsername(item.actor.username) : "Someone";
    const title = item.type === "deck_like"
      ? `${actor} Crystal Liked your deck`
      : item.type === "admin_message"
        ? "Admin notification"
        : `${actor} followed you`;
    const subtitle = item.type === "admin_message"
      ? (item.message || item.created_at_label)
      : (item.deck_title || item.created_at_label);
    row.classList.toggle("is-unread", !item.read);
    row.innerHTML = `
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(subtitle)}</span>
      <small>${escapeHtml(item.created_at_label)}</small>
    `;
    elements.notificationList.append(row);
  }
}

function renderProfile() {
  if (!elements.profileDisplayName) {
    return;
  }

  const viewedProfile = page === "profile" ? state.viewedProfile : null;
  const profile = viewedProfile ?? state.activeProfileDetail ?? activeProfile();
  const ownProfile = activeProfile();
  const viewingOtherProfile = Boolean(viewedProfile && ownProfile && viewedProfile.id !== ownProfile.id);
  const isPublicProfileView = Boolean(viewedProfile) && (!ownProfile || viewedProfile.id !== ownProfile.id);
  document.querySelector(".profile-panel")?.classList.toggle("public-profile-view", isPublicProfileView);
  for (const section of elements.authLoggedOutSections) {
    section.hidden = Boolean(ownProfile);
  }
  for (const section of elements.authLoggedInSections) {
    section.hidden = !ownProfile || Boolean(viewedProfile);
  }

  if (!profile) {
    if (elements.profilePageTitle) {
      elements.profilePageTitle.textContent = "Create and manage your Paladin's Vault identity";
    }
    if (elements.profilePageDescription) {
      elements.profilePageDescription.textContent = "Register your Paladin's Vault identity and use it as the owner for saved decklists.";
    }
    elements.profileDisplayName.textContent = "No registered profile";
    elements.profileHandle.textContent = "Log in or register to save decks.";
    elements.profileBio.textContent = "Create a profile to unlock saved decks, deck ownership, and profile-based navigation.";
    elements.profileDeckCount.textContent = "0";
    elements.profileCardTotal.textContent = "0";
    if (elements.profileFollowerCount) elements.profileFollowerCount.textContent = "0";
    if (elements.profileFollowingCount) elements.profileFollowingCount.textContent = "0";
    elements.profileAvatar.textContent = "CV";
    setAvatarArt(elements.profileAvatar, DEFAULT_LOGO_URL);
    elements.profileAvatar.classList.add("profile-avatar-image");
    if (elements.exploreProfileCard) elements.exploreProfileCard.hidden = true;
    if (elements.profileUsernameInput) elements.profileUsernameInput.value = "";
    return;
  }

  if (elements.profilePageTitle) {
    elements.profilePageTitle.textContent = isPublicProfileView
      ? `${displayUsername(profile.username)}'s public profile`
      : "Create and manage your Paladin's Vault identity";
  }
  if (elements.profilePageDescription) {
    elements.profilePageDescription.textContent = isPublicProfileView
      ? "Browse this player's profile image, description, and published deck library."
      : "Register your Paladin's Vault identity and use it as the owner for saved decklists.";
  }
  elements.profileDisplayName.textContent = displayUsername(profile.username);
  elements.profileHandle.textContent = isPublicProfileView
    ? "Public profile"
    : (profile.email_verified ? "Verified account" : "Email verification required");
  elements.profileBio.textContent = profile.bio || (isPublicProfileView
    ? "This player has not added a profile description yet."
    : (profile.email_verified
      ? "Paladin's Vault profile ready for deck building."
      : "Verify your email to unlock secure account access."));
  const decks = viewedProfile ? viewedProfile.decks : state.profileDecks;
  elements.profileDeckCount.textContent = String(decks.length);
  elements.profileCardTotal.textContent = String(decks.reduce((sum, deck) => sum + deck.card_total, 0));
  if (elements.profileFollowerCount) elements.profileFollowerCount.textContent = String(profile.follower_count ?? 0);
  if (elements.profileFollowingCount) elements.profileFollowingCount.textContent = String(profile.following_count ?? 0);
  if (profile.avatar_url) {
    elements.profileAvatar.textContent = "";
    setAvatarArt(elements.profileAvatar, profile.avatar_url);
    elements.profileAvatar.classList.add("profile-avatar-image");
  } else {
    elements.profileAvatar.textContent = initials(profile.display_name);
    setAvatarArt(elements.profileAvatar, DEFAULT_LOGO_URL);
    elements.profileAvatar.classList.add("profile-avatar-image");
  }
  if (elements.profileAvatarUrlInput) {
    elements.profileAvatarUrlInput.value = profile.avatar_url || "";
  }
  if (elements.profileUsernameInput) {
    elements.profileUsernameInput.value = profile.username || "";
    elements.profileUsernameInput.disabled = Boolean(isPublicProfileView);
  }
  if (elements.saveProfileUsernameButton) {
    elements.saveProfileUsernameButton.hidden = Boolean(isPublicProfileView);
  }
  if (elements.followingList) {
    elements.followingList.replaceChildren();
    const following = state.activeProfileDetail?.following || [];
    if (!ownProfile || following.length === 0) {
      const empty = document.createElement("p");
      empty.className = "hero-text";
      empty.textContent = ownProfile ? "You are not following any profiles yet." : "";
      elements.followingList.append(empty);
    } else {
      for (const followed of following) {
        const tag = document.createElement("a");
        tag.className = "follow-chip";
        tag.href = `/profile?user=${encodeURIComponent(followed.username)}`;
        tag.textContent = displayUsername(followed.username);
        elements.followingList.append(tag);
      }
    }
  }
  if (elements.exploreProfileCard) {
    elements.exploreProfileCard.hidden = !isPublicProfileView;
  }
  if (isPublicProfileView && elements.exploreProfileTitle && elements.exploreProfileMeta && elements.followProfileButton) {
    elements.exploreProfileTitle.textContent = displayUsername(profile.username);
    elements.exploreProfileMeta.textContent = `${profile.follower_count ?? 0} followers • ${profile.following_count ?? 0} following`;
    applyFollowButtonState(elements.followProfileButton, profile.id);
  }
  renderAvatarPresetChoosers();
}

function renderAdminPage() {
  if (page !== "admin") {
    return;
  }
  const loggedInProfile = activeProfile();
  const isAdmin = Boolean(loggedInProfile?.is_admin);
  if (elements.adminDenied) {
    elements.adminDenied.hidden = isAdmin;
  }
  if (elements.adminPanel) {
    elements.adminPanel.hidden = !isAdmin;
  }
  if (!isAdmin || !state.adminOverview) {
    return;
  }

  const overview = state.adminOverview;
  if (elements.adminStatGrid) {
    elements.adminStatGrid.replaceChildren();
    const stats = [
      ["Profiles", overview.total_profiles],
      ["Decks", overview.total_decks],
      ["Public Decks", overview.public_decks],
      ["Private Decks", overview.private_decks],
      ["Banned Profiles", overview.banned_profiles],
    ];
    for (const [label, value] of stats) {
      const card = document.createElement("div");
      card.className = "stat-card";
      card.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong>`;
      elements.adminStatGrid.append(card);
    }
  }

  const renderMonthList = (container, rows) => {
    if (!container) return;
    container.replaceChildren();
    for (const row of rows) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "admin-month-row admin-month-row-button";
      item.innerHTML = `<strong>${escapeHtml(row.label)}</strong><span>${escapeHtml(String(row.count))}</span>`;
      item.addEventListener("click", async () => {
        await openAdminMonthModal(row.label);
      });
      container.append(item);
    }
  };
  renderMonthList(elements.adminUsersByMonth, overview.profiles_by_month || []);
  renderMonthList(elements.adminDecksByMonth, overview.decks_by_month || []);

  if (elements.adminDatabaseTables) {
    elements.adminDatabaseTables.replaceChildren();
    for (const [name, value] of Object.entries(overview.database_tables || {})) {
      const chip = document.createElement("span");
      chip.className = "meta-chip";
      chip.textContent = `${name}: ${value}`;
      elements.adminDatabaseTables.append(chip);
    }
  }

  if (elements.adminEmailDiagnostics) {
    const diagnostics = overview.email_diagnostics || {};
    elements.adminEmailDiagnostics.replaceChildren();
    const cards = [
      ["Mode", diagnostics.delivery_mode || "disabled"],
      ["From", diagnostics.from_email || "Not configured"],
      ["Base URL", diagnostics.app_base_url || "Not configured"],
      ["Resend", diagnostics.resend_configured ? "Configured" : "Missing"],
      ["SMTP fallback", diagnostics.smtp_fallback_configured ? "Configured" : "Missing"],
    ];
    for (const [label, value] of cards) {
      const item = document.createElement("div");
      item.className = "admin-email-row";
      item.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(String(value))}</span>`;
      elements.adminEmailDiagnostics.append(item);
    }
    const lastError = document.createElement("div");
    lastError.className = diagnostics.last_error ? "admin-email-error is-visible" : "admin-email-error";
    lastError.textContent = diagnostics.last_error || "No recent email delivery error recorded.";
    elements.adminEmailDiagnostics.append(lastError);
  }

  if (elements.adminNotifyTarget) {
    const current = elements.adminNotifyTarget.value;
    elements.adminNotifyTarget.innerHTML = '<option value="">All non-banned users</option>';
    for (const profile of overview.all_profiles || []) {
      if (profile.id === state.activeProfileId) continue;
      const option = document.createElement("option");
      option.value = String(profile.id);
      option.textContent = `${displayUsername(profile.username)}${profile.is_banned ? " (banned)" : ""}`;
      elements.adminNotifyTarget.append(option);
    }
    elements.adminNotifyTarget.value = current;
  }

  if (elements.adminEmailTarget) {
    const current = elements.adminEmailTarget.value;
    elements.adminEmailTarget.innerHTML = '<option value="">Select a user</option>';
    for (const profile of overview.all_profiles || []) {
      if (profile.is_banned || !profile.email || profile.id === state.activeProfileId) {
        continue;
      }
      const option = document.createElement("option");
      option.value = String(profile.id);
      option.textContent = `${displayUsername(profile.username)} • ${profile.email}`;
      elements.adminEmailTarget.append(option);
    }
    elements.adminEmailTarget.value = current;
  }

  if (elements.adminUserList) {
    elements.adminUserList.replaceChildren();
    for (const profile of overview.all_profiles || []) {
      const row = document.createElement("article");
      row.className = "admin-user-row";
      row.innerHTML = `
        <div class="admin-user-copy">
          <strong>${escapeHtml(displayUsername(profile.username))}</strong>
          <p>${escapeHtml(profile.email || "No email")}</p>
          <small>${profile.is_admin ? "Admin" : "User"} • ${profile.is_banned ? "Banned" : "Active"} • ${profile.email_verified ? "Verified" : "Unverified"}</small>
        </div>
      `;
      const actions = document.createElement("div");
      actions.className = "admin-user-actions";
      if (!profile.is_admin && profile.id !== state.activeProfileId) {
        if (!profile.email_verified) {
          const verifyButton = document.createElement("button");
          verifyButton.type = "button";
          verifyButton.className = "primary-button";
          verifyButton.textContent = "Verify";
          verifyButton.addEventListener("click", async () => {
            await verifyAdminUser(profile.id);
          });
          actions.append(verifyButton);
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = profile.is_banned ? "ghost-button" : "danger-button";
        button.textContent = profile.is_banned ? "Unban" : "Ban";
        button.addEventListener("click", async () => {
          const reason = profile.is_banned ? "" : window.prompt(`Ban reason for ${displayUsername(profile.username)}:`) || "";
          await toggleAdminBan(profile.id, !profile.is_banned, reason);
        });
        actions.append(button);
      }
      row.append(actions);
      elements.adminUserList.append(row);
    }
  }

  if (elements.adminDeckList) {
    elements.adminDeckList.replaceChildren();
    for (const deck of overview.recent_decks || []) {
      elements.adminDeckList.append(buildDeckSummaryCard(deck));
    }
  }

  if (elements.adminContactInbox) {
    elements.adminContactInbox.replaceChildren();
    for (const item of overview.recent_contact_messages || []) {
      const row = document.createElement("article");
      row.className = "admin-message-card";
      row.innerHTML = `
        <div class="admin-message-head">
          <strong>${escapeHtml(item.subject || "Message")}</strong>
          <span>${escapeHtml(item.created_at_label || "")}</span>
        </div>
      `;
      const meta = document.createElement("p");
      meta.className = "admin-message-meta";
      meta.innerHTML = `<strong>${escapeHtml(displayUsername(item.username || "user"))}</strong> • ${escapeHtml(item.email || "")}`;
      const body = document.createElement("p");
      body.className = "admin-message-body";
      body.textContent = item.message || "";
      row.append(meta, body);
      elements.adminContactInbox.append(row);
    }
    if (!(overview.recent_contact_messages || []).length) {
      const empty = document.createElement("p");
      empty.className = "hero-text";
      empty.textContent = "No user messages yet.";
      elements.adminContactInbox.append(empty);
    }
  }

  if (elements.adminAuditLog) {
    elements.adminAuditLog.replaceChildren();
    for (const item of overview.audit_log || []) {
      const row = document.createElement("article");
      row.className = "admin-audit-entry";
      row.innerHTML = `
        <div class="admin-audit-head">
          <strong>${escapeHtml(item.action || "action")}</strong>
          <span>${escapeHtml(item.created_at || "")}</span>
        </div>
      `;
      const detail = document.createElement("p");
      detail.className = "admin-audit-detail";
      detail.textContent = item.detail || (item.target_profile_id ? `Target profile ID: ${item.target_profile_id}` : "No extra detail.");
      row.append(detail);
      elements.adminAuditLog.append(row);
    }
  }
}

function renderProfileDecks() {
  if (!elements.profileDecks) {
    return;
  }
  elements.profileDecks.replaceChildren();
  if (elements.likedDecks) {
    elements.likedDecks.replaceChildren();
  }
  const ownProfile = activeProfile();
  const viewedProfile = page === "profile" ? state.viewedProfile : null;
  const decks = viewedProfile ? viewedProfile.decks : state.profileDecks;
  const likedDecks = viewedProfile ? (viewedProfile.liked_decks || []) : state.likedDecks;
  const viewingOwnProfile = !viewedProfile || (ownProfile && viewedProfile.id === ownProfile.id);

  if (elements.profileDecksTitle) {
    elements.profileDecksTitle.textContent = viewedProfile && !viewingOwnProfile
      ? `Decks by ${displayUsername(viewedProfile.username)}`
      : "Saved decks";
  }
  if (elements.likedDecksTitle) {
    elements.likedDecksTitle.textContent = viewedProfile && !viewingOwnProfile
      ? `Liked Decks by ${displayUsername(viewedProfile.username)}`
      : "Liked decks";
  }

  if (!ownProfile && !viewedProfile) {
    const message = document.createElement("p");
    message.className = "hero-text";
    message.textContent = "My Decks is only available for registered profiles. Create a profile first.";
    elements.profileDecks.append(message);
    return;
  }

  if (decks.length === 0) {
    const message = document.createElement("p");
    message.className = "hero-text";
    message.textContent = viewedProfile && !viewingOwnProfile
      ? "This profile has no saved decks yet."
      : "You have no saved decks yet.";
    elements.profileDecks.append(message);
    return;
  }

  for (const deck of decks) {
    elements.profileDecks.append(buildDeckSummaryCard(deck));
  }

  if (elements.likedDecks) {
    if (likedDecks.length === 0) {
      const message = document.createElement("p");
      message.className = "hero-text";
      message.textContent = viewedProfile && !viewingOwnProfile
        ? "This profile has not liked any decks yet."
        : "You have not liked any decks yet.";
      elements.likedDecks.append(message);
    } else {
      for (const deck of likedDecks) {
        elements.likedDecks.append(buildDeckSummaryCard(deck));
      }
    }
  }
}

function renderExploreDecks() {
  if (!elements.exploreDecks) {
    return;
  }
  elements.exploreDecks.replaceChildren();

  const filteredDecks = state.exploreDecks.filter((deck) => {
    const haystack = `${deck.title} ${normalizedUsername(deck.owner?.username || "")}`.toLowerCase();
    const matchesSearch = !state.exploreSearch || haystack.includes(state.exploreSearch);
    const matchesOwner = !state.exploreDeckFilters.owner
      || normalizedUsername(deck.owner?.username || "").includes(state.exploreDeckFilters.owner);
    const matchesCivilization = state.exploreDeckFilters.civilization === "all"
      || (deck.civilizations || []).includes(state.exploreDeckFilters.civilization);
    const matchesCard = !state.exploreDeckFilters.containsCard
      || (deck.card_names || []).some((name) => name.toLowerCase().includes(state.exploreDeckFilters.containsCard));
    return matchesSearch && matchesOwner && matchesCivilization && matchesCard;
  });

  if (filteredDecks.length === 0) {
    const message = document.createElement("p");
    message.className = "hero-text";
    message.textContent = (state.exploreSearch || state.exploreDeckFilters.owner || state.exploreDeckFilters.containsCard || state.exploreDeckFilters.civilization !== "all")
      ? "No decks matched the current filters."
      : "No saved decks have been published yet.";
    elements.exploreDecks.append(message);
    return;
  }

  for (const deck of filteredDecks) {
    elements.exploreDecks.append(buildDeckSummaryCard(deck));
  }
}

function buildDeckSummaryCard(deck) {
  const article = document.createElement("article");
  article.className = "profile-deck-card";
  article.style.setProperty("--deck-card-cover", deck.cover_image_url ? `url('${escapeHtml(deck.cover_image_url)}')` : "none");
  const isOwnDeck = Boolean(state.activeProfileId && deck.owner?.id === state.activeProfileId);
  article.innerHTML = `
    <div class="profile-deck-cover" style="background-image: url('${escapeHtml(deck.cover_image_url || DEFAULT_LOGO_URL)}')"></div>
    <strong>${escapeHtml(deck.title)}</strong>
    <span>${deck.card_total} cards • ${deck.updated_at_label}</span>
    <small>${deck.owner ? `by ${escapeHtml(displayUsername(deck.owner.username))}` : "Community deck"}</small>
  `;

  const likeMeta = document.createElement("div");
  likeMeta.className = "deck-like-meta";
  const likeCount = document.createElement("span");
  likeCount.className = "deck-like-count";
  likeCount.textContent = `${deck.like_count || 0} like${(deck.like_count || 0) === 1 ? "" : "s"}`;
  likeMeta.append(likeCount);
  if (deck.liked_by?.length) {
    const likedBy = document.createElement("div");
    likedBy.className = "deck-liked-by";
    for (const profile of deck.liked_by.slice(0, 4)) {
      const chip = document.createElement("span");
      chip.className = "deck-like-chip";
      chip.textContent = displayUsername(profile.username);
      likedBy.append(chip);
    }
    if (deck.liked_by.length > 4) {
      const more = document.createElement("span");
      more.className = "deck-like-chip";
      more.textContent = `+${deck.liked_by.length - 4}`;
      likedBy.append(more);
    }
    likeMeta.append(likedBy);
  }
  article.append(likeMeta);

  const actions = document.createElement("div");
  actions.className = "profile-deck-actions";
  article.addEventListener("click", () => {
    window.location.href = deck.share_url || `/share/${deck.public_id}`;
  });

  if (state.activeProfileId && !isOwnDeck) {
    const likeButton = document.createElement("button");
    likeButton.type = "button";
    likeButton.className = deck.liked_by_viewer
      ? "like-button is-liked profile-inline-button"
      : "like-button profile-inline-button";
    likeButton.textContent = deck.liked_by_viewer ? "Crystal Liked" : "Crystal Like";
    likeButton.addEventListener("click", async (event) => {
      event.stopPropagation();
      await toggleDeckLike(deck.public_id);
    });
    actions.append(likeButton);
  }

  if (isOwnDeck) {
    const duplicateButton = document.createElement("button");
    duplicateButton.type = "button";
    duplicateButton.className = "primary-button profile-inline-button";
    duplicateButton.textContent = "Duplicate";
    duplicateButton.addEventListener("click", async (event) => {
      event.stopPropagation();
      await duplicateDeckToProfile(deck.public_id);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "danger-button profile-inline-button";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      openDeckDeleteModal(deck);
    });
    actions.append(duplicateButton);
    actions.append(deleteButton);
  } else if (state.activeProfileId) {
    const duplicateButton = document.createElement("button");
    duplicateButton.type = "button";
    duplicateButton.className = "primary-button profile-inline-button";
    duplicateButton.textContent = "Duplicate";
    duplicateButton.addEventListener("click", async (event) => {
      event.stopPropagation();
      await duplicateDeckToProfile(deck.public_id);
    });
    actions.append(duplicateButton);
  }

  if (actions.childElementCount > 0) {
    article.append(actions);
  }
  return article;
}

function renderExploreUsers() {
  if (!elements.exploreUsers) {
    return;
  }
  elements.exploreUsers.replaceChildren();

  const ownProfile = activeProfile();
  const others = state.profiles
    .filter((profile) => !profile.is_admin)
    .filter((profile) => !ownProfile || profile.id !== ownProfile.id)
    .filter((profile) => {
      if (!state.exploreSearch) return true;
      return normalizedUsername(profile.username).includes(state.exploreSearch);
    });
  if (others.length === 0) {
    const message = document.createElement("p");
    message.className = "hero-text";
    message.textContent = state.exploreSearch
      ? "No users matched the current filter."
      : "No other profiles are available yet.";
    elements.exploreUsers.append(message);
    return;
  }

  for (const profile of others) {
    const card = document.createElement("article");
    card.className = "profile-deck-card";
    card.innerHTML = `
      <div class="profile-user-avatar"></div>
      <strong>${escapeHtml(displayUsername(profile.username))}</strong>
      <span>${profile.follower_count ?? 0} followers • ${profile.following_count ?? 0} following</span>
    `;
    setAvatarArt(card.querySelector(".profile-user-avatar"), profile.avatar_url || DEFAULT_LOGO_URL);
    const actions = document.createElement("div");
    actions.className = "hero-actions";
    const viewButton = document.createElement("a");
    viewButton.className = "ghost-button";
    viewButton.href = `/profile?user=${encodeURIComponent(profile.username)}`;
    viewButton.textContent = "Open Profile";
    actions.append(viewButton);
    if (ownProfile) {
      const followButton = document.createElement("button");
      followButton.type = "button";
      followButton.className = "primary-button";
      applyFollowButtonState(followButton, profile.id);
      followButton.addEventListener("click", async () => {
        await toggleFollowProfile(profile.id);
      });
      actions.append(followButton);
    }
    card.append(actions);
    elements.exploreUsers.append(card);
  }
}

function renderAvatarPresetChoosers() {
  renderAvatarPreview(elements.registerAvatarPreview, elements.registerAvatarUrl);
  renderAvatarPreview(elements.profileAvatarPreview, elements.profileAvatarUrlInput);
  renderAvatarPickerBrowser();
}

function renderAvatarPreview(container, input) {
  if (!container || !input) {
    return;
  }
  container.replaceChildren();
  const preview = document.createElement("div");
  preview.className = "avatar-preview-card";
  setAvatarArt(preview, input.value || DEFAULT_LOGO_URL);
  container.append(preview);
}

function renderAvatarPickerBrowser() {
  const container = elements.avatarPickerBrowser;
  const input = state.avatarPickerTarget === "profile" ? elements.profileAvatarUrlInput : elements.registerAvatarUrl;
  if (!container || !input) {
    return;
  }
  container.replaceChildren();

  for (const [civilization, names] of Object.entries(AVATAR_PRESETS)) {
    const section = document.createElement("section");
    section.className = "avatar-preset-section";

    const title = document.createElement("p");
    title.className = "section-label";
    title.textContent = civilization;
    section.append(title);

    const grid = document.createElement("div");
    grid.className = "avatar-preset-grid";

    for (const name of names) {
      const card = resolveCardByText(name);
      if (!card) {
        continue;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "avatar-preset-card";
      const avatarValue = buildAvatarPresetValue(card, name);
      button.classList.toggle("is-selected", input.value === avatarValue);
      button.style.setProperty("--avatar-accent", avatarCivilizationAccent(civilization));
      button.innerHTML = `
        <div class="avatar-preset-art"></div>
        <small>${escapeHtml(card.name)}</small>
      `;
      setAvatarArt(button.querySelector(".avatar-preset-art"), avatarValue || DEFAULT_LOGO_URL);
      button.addEventListener("click", async () => {
        input.value = avatarValue || "";
        if (state.avatarPickerTarget === "profile" && state.activeProfileId) {
          applyLocalAvatarUpdate(avatarValue || null);
        } else {
          renderAvatarPresetChoosers();
        }
        if (state.avatarPickerTarget === "profile" && state.activeProfileId) {
          await saveProfileAvatar(avatarValue || null, { silent: true });
        }
        closeAvatarPickerModal();
      });
      grid.append(button);
    }

    section.append(grid);
    container.append(section);
  }
}

function buildAvatarPresetValue(card, preferredName = "") {
  const sourceName = preferredName || card?.name;
  if (!sourceName) {
    return "";
  }
  const cropped = `/assets/assets/logo_cropped/${avatarAssetSlug(sourceName)}.png`;
  const knownCroppedAvatarSlugs = new Set([
    "alcadeias-lord-of-spirits",
    "aqua-guard",
    "aqua-hulcus",
    "aqua-sniper",
    "armored-blaster-valdios",
    "ballom-master-of-death",
    "billion-degree-dragon",
    "bolmeteus-steel-dragon",
    "bolshack-dragon",
    "brawler-zyler",
    "bronze-arm-tribe",
    "charmilia-the-enticer",
    "craze-valkyrie-the-drastic",
    "crystal-paladin",
    "deadly-fighter-braid-claw",
    "deathliger-lion-of-chaos",
    "emeral",
    "fighter-dual-fang",
    "king-tsunami",
    "la-ura-giga",
    "marrow-ooze-the-twister",
    "miar-comet-elemental",
    "phantasmal-horror-gigazald",
    "propeller-mutant",
    "quixotic-hero-swine-snout",
    "sarius-vizier-of-suppression",
    "super-necrodragon-abzo-dolba",
    "super-terradragon-bailas-gale"
  ]);
  if (knownCroppedAvatarSlugs.has(avatarAssetSlug(sourceName))) {
    return cropped;
  }
  return resolveAssetUrl(card?.image_path || card?.illustration_path || cropped);
}

function avatarAssetSlug(name) {
  return normalizeName(name).replace(/\s+/g, "-");
}

function avatarCivilizationAccent(civilization) {
  const accents = {
    Water: "rgba(104, 202, 255, 0.88)",
    Darkness: "rgba(172, 114, 220, 0.88)",
    Light: "rgba(255, 232, 153, 0.92)",
    Nature: "rgba(132, 205, 120, 0.9)",
    Fire: "rgba(255, 132, 92, 0.92)"
  };
  return accents[civilization] || "rgba(168, 220, 255, 0.72)";
}

function applyLocalAvatarUpdate(avatarUrl) {
  if (!state.activeProfileId) {
    return;
  }
  state.profiles = state.profiles.map((profile) => (
    profile.id === state.activeProfileId
      ? { ...profile, avatar_url: avatarUrl }
      : profile
  ));
  if (state.activeProfileDetail?.id === state.activeProfileId) {
    state.activeProfileDetail = { ...state.activeProfileDetail, avatar_url: avatarUrl };
  }
  if (state.viewedProfile?.id === state.activeProfileId) {
    state.viewedProfile = { ...state.viewedProfile, avatar_url: avatarUrl };
  }
  renderWelcome();
  renderAuthNavigation();
  renderProfile();
  renderAvatarPresetChoosers();
}

function parseAvatarFocus(url) {
  const match = String(url || "").match(/#avatar=(\d+(?:\.\d+)?),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)/);
  if (!match) {
    return { cleanUrl: url, x: 50, y: 50, zoom: 100, hasArtCrop: false };
  }
  return {
    cleanUrl: String(url).replace(/#avatar=[^#]+$/, ""),
    x: Number(match[1]),
    y: Number(match[2]),
    zoom: Number(match[3]),
    hasArtCrop: true
  };
}

function setAvatarArt(element, url, options = {}) {
  if (!element) {
    return;
  }
  const focus = parseAvatarFocus(url);
  const zoomFactor = Number(options.zoomFactor ?? 1);
  const artOnlyFactor = Number(options.artOnlyFactor ?? 1.42);
  const finalZoom = focus.hasArtCrop
    ? focus.zoom * zoomFactor * artOnlyFactor
    : focus.zoom * zoomFactor;
  const finalY = focus.hasArtCrop
    ? Math.max(6, focus.y - 11)
    : focus.y;
  element.style.backgroundImage = `url('${focus.cleanUrl || DEFAULT_LOGO_URL}')`;
  element.style.backgroundSize = `${finalZoom}%`;
  element.style.backgroundPosition = `${focus.x}% ${finalY}%`;
  element.style.backgroundRepeat = "no-repeat";
}

function openAvatarPicker(target) {
  state.avatarPickerTarget = target;
  renderAvatarPickerBrowser();
  if (elements.avatarPickerModal) {
    elements.avatarPickerModal.hidden = false;
  }
}

function closeAvatarPickerModal() {
  if (elements.avatarPickerModal) {
    elements.avatarPickerModal.hidden = true;
  }
}

function openAuthModal() {
  closeSignupModal();
  setAuthModalStatus("", "info", null, "login");
  setLoginModalAuxActions(false);
  if (elements.authModal) {
    elements.authModal.hidden = false;
  }
}

function closeAuthModal() {
  setAuthModalStatus("", "info", null, "login");
  setLoginModalAuxActions(false);
  if (elements.authModal) {
    elements.authModal.hidden = true;
  }
}

function openSignupModal() {
  closeAuthModal();
  setAuthModalStatus("", "info", null, "signup");
  if (elements.signupModal) {
    elements.signupModal.hidden = false;
  }
}

function closeSignupModal() {
  setAuthModalStatus("", "info", null, "signup");
  if (elements.signupModal) {
    elements.signupModal.hidden = true;
  }
}

function openExploreFiltersModal() {
  if (elements.exploreFilterCardInput) {
    elements.exploreFilterCardInput.value = state.exploreDeckFilters.containsCard;
  }
  if (elements.exploreFilterOwnerInput) {
    elements.exploreFilterOwnerInput.value = state.exploreDeckFilters.owner;
  }
  if (elements.exploreFilterCivilizationSelect) {
    elements.exploreFilterCivilizationSelect.value = state.exploreDeckFilters.civilization;
  }
  if (elements.exploreFiltersModal) {
    elements.exploreFiltersModal.hidden = false;
  }
}

function closeExploreFiltersModal() {
  if (elements.exploreFiltersModal) {
    elements.exploreFiltersModal.hidden = true;
  }
}

function applyExploreFilters() {
  state.exploreDeckFilters.containsCard = elements.exploreFilterCardInput?.value.trim().toLowerCase() || "";
  state.exploreDeckFilters.owner = elements.exploreFilterOwnerInput?.value.trim().toLowerCase() || "";
  state.exploreDeckFilters.civilization = elements.exploreFilterCivilizationSelect?.value || "all";
  renderExploreDecks();
  closeExploreFiltersModal();
}

function resetExploreFilters() {
  state.exploreDeckFilters = { containsCard: "", owner: "", civilization: "all" };
  if (elements.exploreFilterCardInput) elements.exploreFilterCardInput.value = "";
  if (elements.exploreFilterOwnerInput) elements.exploreFilterOwnerInput.value = "";
  if (elements.exploreFilterCivilizationSelect) elements.exploreFilterCivilizationSelect.value = "all";
  renderExploreDecks();
}

function ensureAuthModalEnhancements() {
  if (!elements.authModal) {
    return;
  }
  const ensureStatusNode = (modal, id) => {
    if (!modal || modal.querySelector(`#${id}`)) {
      return modal?.querySelector(`#${id}`) || null;
    }
    const grid = modal.querySelector(".create-profile-grid");
    if (!grid) return null;
    const status = document.createElement("p");
    status.id = id;
    status.className = "hero-text auth-inline-status";
    grid.append(status);
    return status;
  };

  elements.authModalStatus = ensureStatusNode(elements.authModal, "auth-modal-status");
  elements.signupModalStatus = ensureStatusNode(elements.signupModal, "signup-modal-status");

  if (elements.resendVerificationButton && elements.loginSignupShortcutButton) {
    return;
  }
  const loginButton = elements.loginButton;
  if (!loginButton) {
    return;
  }
  const actionRow = document.createElement("div");
  actionRow.className = "hero-actions";
  loginButton.insertAdjacentElement("afterend", actionRow);

  const signupButton = document.createElement("button");
  signupButton.type = "button";
  signupButton.id = "login-signup-shortcut-button";
  signupButton.className = "ghost-button";
  signupButton.textContent = "Sign Up";
  signupButton.addEventListener("click", openSignupModal);
  actionRow.append(signupButton);
  elements.loginSignupShortcutButton = signupButton;

  const button = document.createElement("button");
  button.type = "button";
  button.id = "resend-verification-button";
  button.className = "ghost-button";
  button.textContent = "Resend Verification Email";
  button.hidden = true;
  button.style.display = "none";
  actionRow.append(button);
  elements.resendVerificationButton = button;
}

function setLoginModalAuxActions(showResend = false) {
  if (elements.resendVerificationButton) {
    elements.resendVerificationButton.hidden = !showResend;
    elements.resendVerificationButton.style.display = showResend ? "" : "none";
  }
  if (elements.loginSignupShortcutButton) {
    elements.loginSignupShortcutButton.hidden = showResend;
    elements.loginSignupShortcutButton.style.display = showResend ? "none" : "";
  }
}

function setAuthModalStatus(message, type = "info", action = null, target = "login") {
  const node = target === "signup" ? elements.signupModalStatus : elements.authModalStatus;
  if (!node) {
    return;
  }
  node.replaceChildren();
  if (message) {
    node.append(document.createTextNode(message));
  }
  if (action?.href && action?.label) {
    node.append(document.createTextNode(" "));
    const link = document.createElement("a");
    link.href = action.href;
    link.textContent = action.label;
    link.className = "status-action-link";
    node.append(link);
  }
  node.classList.remove("status-success", "status-error");
  if (type === "success") node.classList.add("status-success");
  if (type === "error") node.classList.add("status-error");
}

function renderStatusFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const verification = params.get("verification");
  if (!verification) {
    return;
  }
  if (verification === "success") {
    setStatus("Your email has been verified. You can now log in.", "success");
  } else if (verification === "expired") {
    setStatus("That verification link has expired. Request a new verification email.", "error");
  } else if (verification === "invalid") {
    setStatus("That verification link is invalid or has already been used.", "error");
  }
  params.delete("verification");
  const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash || ""}`;
  window.history.replaceState({}, "", next);
}

function maybeOpenAccountDeleteFromQuery() {
  const params = new URLSearchParams(window.location.search);
  if (page !== "profile" || params.get("deleteAccount") !== "1" || !state.activeProfileId || state.viewedProfile) {
    return;
  }
  openAccountDeleteModal();
  params.delete("deleteAccount");
  const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash || ""}`;
  window.history.replaceState({}, "", next);
}

function ensureDeckDeleteModal() {
  if (elements.deckDeleteModal) {
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="deck-delete-modal" class="modal-shell" hidden>
      <div class="modal-backdrop" data-close-deck-delete-modal></div>
      <section class="panel modal-panel auth-modal-panel">
        <div class="panel-header">
          <div>
            <p class="section-label">Delete Deck</p>
            <h2>Are you sure?</h2>
          </div>
          <button id="close-deck-delete-modal" type="button" class="ghost-button">Close</button>
        </div>
        <p id="deck-delete-message" class="hero-text">This action cannot be undone.</p>
        <div class="hero-actions">
          <button id="confirm-deck-delete-button" class="primary-button danger-button">Delete Deck</button>
          <button type="button" class="ghost-button" data-close-deck-delete-modal>Cancel</button>
        </div>
      </section>
    </div>
  `;
  document.body.append(wrapper.firstElementChild);
  elements.deckDeleteModal = document.querySelector("#deck-delete-modal");
  elements.closeDeckDeleteModal = document.querySelector("#close-deck-delete-modal");
  elements.closeDeckDeleteTargets = [...document.querySelectorAll("[data-close-deck-delete-modal]")];
  elements.confirmDeckDeleteButton = document.querySelector("#confirm-deck-delete-button");
  elements.deckDeleteMessage = document.querySelector("#deck-delete-message");
}

function ensureAccountDeleteModal() {
  if (document.querySelector("#account-delete-modal")) {
    elements.accountDeleteModal = document.querySelector("#account-delete-modal");
    elements.closeAccountDeleteModal = document.querySelector("#close-account-delete-modal");
    elements.closeAccountDeleteTargets = [...document.querySelectorAll("[data-close-account-delete-modal]")];
    elements.confirmAccountDeleteButton = document.querySelector("#confirm-account-delete-button");
    elements.accountDeletePassword = document.querySelector("#account-delete-password");
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="account-delete-modal" class="modal-shell" hidden>
      <div class="modal-backdrop" data-close-account-delete-modal></div>
      <section class="panel modal-panel auth-modal-panel account-delete-modal-panel">
        <div class="panel-header">
          <div>
            <p class="section-label">Delete Account</p>
            <h2>Are you sure?</h2>
          </div>
          <button id="close-account-delete-modal" type="button" class="ghost-button">Close</button>
        </div>
        <div class="account-delete-warning">
          <strong>Are you sure you want to delete this user?</strong>
          <p id="account-delete-message" class="hero-text">This will permanently delete your user, owned decks, likes, follows, and notifications. This action cannot be undone.</p>
        </div>
        <label class="field">
          <span>Password</span>
          <input id="account-delete-password" type="password" placeholder="Confirm your password">
        </label>
        <div class="hero-actions">
          <button id="confirm-account-delete-button" class="primary-button danger-button">Delete Account</button>
          <button type="button" class="ghost-button" data-close-account-delete-modal>Cancel</button>
        </div>
      </section>
    </div>
  `;
  document.body.append(wrapper.firstElementChild);
  elements.accountDeleteModal = document.querySelector("#account-delete-modal");
  elements.closeAccountDeleteModal = document.querySelector("#close-account-delete-modal");
  elements.closeAccountDeleteTargets = [...document.querySelectorAll("[data-close-account-delete-modal]")];
  elements.confirmAccountDeleteButton = document.querySelector("#confirm-account-delete-button");
  elements.accountDeletePassword = document.querySelector("#account-delete-password");
  elements.closeAccountDeleteModal?.addEventListener("click", closeAccountDeleteModal);
  for (const target of elements.closeAccountDeleteTargets) {
    target.addEventListener("click", closeAccountDeleteModal);
  }
  elements.confirmAccountDeleteButton?.addEventListener("click", deleteAccount);
}

function openAccountDeleteModal() {
  if (!state.activeProfileId || !elements.accountDeleteModal) {
    return;
  }
  if (elements.accountDeletePassword) {
    elements.accountDeletePassword.value = "";
  }
  elements.accountDeleteModal.hidden = false;
}

function closeAccountDeleteModal() {
  if (elements.accountDeleteModal) {
    elements.accountDeleteModal.hidden = true;
  }
}

async function deleteAccount() {
  if (!state.activeProfileId) {
    setStatus("Log in first to manage your account.", "error");
    return;
  }
  const password = elements.accountDeletePassword?.value ?? "";
  if (!password) {
    setStatus("Enter your password to delete your account.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/profiles/${state.activeProfileId}/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password })
    });
    closeAccountDeleteModal();
    logoutProfile();
    state.viewedProfile = null;
    state.activeProfileDetail = null;
    state.profileDecks = [];
    state.likedDecks = [];
    await hydrateProfiles();
    renderExploreUsers();
    renderExploreDecks();
    setStatus(payload.message || "Account deleted.", "success");
  } catch (error) {
    setStatus(error.message || "Account deletion failed.", "error");
  }
}

function ensureCookieConsentBanner() {
  if (window.localStorage.getItem(COOKIE_CONSENT_KEY)) {
    return;
  }
  if (document.querySelector("#cookie-consent-banner")) {
    return;
  }
  const banner = document.createElement("aside");
  banner.id = "cookie-consent-banner";
  banner.className = "cookie-consent-banner panel";
  banner.innerHTML = `
    <div class="cookie-consent-copy">
      <strong>Privacy notice</strong>
      <p>Paladin's Vault uses essential browser storage for login state, deck workspace data, preferences, and account security flows. No optional analytics cookies are enabled right now.</p>
    </div>
    <div class="cookie-consent-actions">
      <a class="ghost-button" href="/privacy">Privacy Policy</a>
      <button type="button" class="primary-button" id="accept-cookie-consent">Understood</button>
    </div>
  `;
  document.body.append(banner);
  document.querySelector("#accept-cookie-consent")?.addEventListener("click", () => {
    window.localStorage.setItem(COOKIE_CONSENT_KEY, "accepted");
    banner.remove();
  });
}

function openDeckDeleteModal(deck) {
  state.deleteDeckTarget = deck;
  if (elements.deckDeleteMessage) {
    elements.deckDeleteMessage.textContent = `Are you sure you want to delete "${deck.title}"? This action cannot be undone.`;
  }
  if (elements.deckDeleteModal) {
    elements.deckDeleteModal.hidden = false;
  }
}

function closeDeckDeleteModal() {
  state.deleteDeckTarget = null;
  if (elements.deckDeleteModal) {
    elements.deckDeleteModal.hidden = true;
  }
}

async function confirmDeleteDeck() {
  const deck = state.deleteDeckTarget;
  if (!deck || !state.activeProfileId) {
    closeDeckDeleteModal();
    return;
  }
  await fetchJson(`${API_BASE}/decks/${deck.public_id}?profile_id=${state.activeProfileId}`, {
    method: "DELETE"
  });
  if (state.loadedShareId === deck.public_id) {
    state.loadedShareId = null;
    state.deck = {};
    persistDeckSnapshot();
  }
  await loadProfileDecks(state.activeProfileId);
  if (needsExploreDecks(page)) {
    await loadExploreDecks();
    renderExploreDecks();
  }
  renderProfile();
  renderProfileDecks();
  renderBuilderDeckOptions();
  renderPrintDeckOptions();
  closeDeckDeleteModal();
  setStatus(`Deleted deck: ${deck.title}`, "success");
}

function handleNavDropdownToggle(dropdown) {
  const menu = getDropdownMenu(dropdown);
  const summary = dropdown.querySelector("summary");
  if (!menu || !summary) {
    return;
  }
  if (!dropdown.open) {
    restoreDropdownMenu(dropdown, menu);
    return;
  }
  for (const other of elements.navDropdowns) {
    if (other !== dropdown && other.open) {
      other.open = false;
    }
  }
  if (window.innerWidth <= 820) {
    restoreDropdownMenu(dropdown, menu);
    return;
  }
  promoteDropdownMenu(dropdown, menu);
  positionDropdownMenu(summary, menu, dropdown.classList.contains("nav-avatar-dropdown"));
}

function repositionOpenNavDropdowns() {
  if (window.innerWidth <= 820) {
    return;
  }
  for (const dropdown of elements.navDropdowns) {
    if (!dropdown.open) {
      continue;
    }
    const menu = getDropdownMenu(dropdown);
    const summary = dropdown.querySelector("summary");
    if (!menu || !summary) {
      continue;
    }
    positionDropdownMenu(summary, menu, dropdown.classList.contains("nav-avatar-dropdown"));
  }
}

function promoteDropdownMenu(dropdown, menu) {
  if (!menu.dataset.originalParent) {
    menu.dataset.originalParent = "nav-dropdown";
  }
  menu._ownerDropdown = dropdown;
  if (menu.parentElement !== document.body) {
    document.body.append(menu);
    menu.classList.add("is-floating");
  }
}

function restoreDropdownMenu(dropdown, menu) {
  if (menu.parentElement !== dropdown) {
    dropdown.append(menu);
  }
  menu.classList.remove("is-floating");
  menu.style.position = "";
  menu.style.top = "";
  menu.style.left = "";
  menu.style.right = "";
  menu.style.width = "";
  menu.style.maxHeight = "";
}

function getDropdownMenu(dropdown) {
  return dropdown.querySelector(".nav-dropdown-menu")
    || [...document.querySelectorAll(".nav-dropdown-menu.is-floating")].find((menu) => menu._ownerDropdown === dropdown)
    || null;
}

function positionDropdownMenu(summary, menu, alignRight = false) {
  const rect = summary.getBoundingClientRect();
  const menuWidth = Math.max(menu.scrollWidth || menu.offsetWidth || 280, 280);
  let left = alignRight ? rect.right - menuWidth : rect.left;
  left = Math.max(12, Math.min(left, window.innerWidth - menuWidth - 12));
  menu.style.position = "fixed";
  menu.style.top = `${rect.bottom + 8}px`;
  menu.style.left = `${left}px`;
  menu.style.right = "auto";
  menu.style.width = `${menuWidth}px`;
  menu.style.maxHeight = `${Math.max(window.innerHeight - rect.bottom - 24, 120)}px`;
}

function handleDocumentClick(event) {
  if (
    state.playtestSelected
    && elements.playtestActionOverlay
    && !elements.playtestActionOverlay.hidden
    && !elements.playtestActionOverlay.contains(event.target)
    && !event.target.closest(".playtest-card")
    && !event.target.closest(".playtest-deck-stack")
  ) {
    state.playtestSelected = null;
    renderPlaytestSandbox();
  }
  if (
    elements.playtestSearchResults
    && !elements.playtestSearchResults.contains(event.target)
    && !elements.playtestSearchInput?.contains(event.target)
  ) {
    elements.playtestSearchResults.hidden = true;
  }
  if (
    elements.searchSuggestions
    && !elements.searchSuggestions.contains(event.target)
    && !elements.searchInput?.contains(event.target)
  ) {
    elements.searchSuggestions.hidden = true;
  }
  for (const dropdown of elements.navDropdowns) {
    const menu = getDropdownMenu(dropdown);
    const summary = dropdown.querySelector("summary");
    if (!dropdown.open || !menu || !summary) {
      continue;
    }
    const clickedInsideMenu = menu.contains(event.target);
    const clickedSummary = summary.contains(event.target);
    if (!clickedInsideMenu && !clickedSummary) {
      dropdown.open = false;
    }
  }
}

function isProfileFollowed(profileId) {
  if (state.viewedProfile?.id === profileId) {
    return Boolean(state.viewedProfile.followed_by_viewer);
  }
  const listedProfile = state.profiles.find((profile) => profile.id === profileId);
  if (listedProfile) {
    return Boolean(listedProfile.followed_by_viewer);
  }
  return Boolean(state.activeProfileDetail?.following?.some((profile) => profile.id === profileId));
}

function applyFollowButtonState(button, profileId) {
  if (!button) {
    return;
  }
  const ownId = state.activeProfileId;
  const isOwnProfile = Boolean(ownId && ownId === profileId);
  const followed = isProfileFollowed(profileId);
  button.hidden = isOwnProfile;
  button.textContent = followed ? "Unfollow" : "Follow";
  button.classList.toggle("is-unfollow", followed);
  button.classList.toggle("primary-button", !followed);
  button.classList.toggle("danger-button", followed);
  button.classList.remove("ghost-button");
}

function setProfileFollowState(profileId, followed) {
  state.profiles = state.profiles.map((profile) => {
    if (profile.id !== profileId) {
      return profile;
    }
    const currentFollowed = Boolean(profile.followed_by_viewer);
    const followerDelta = followed === currentFollowed ? 0 : (followed ? 1 : -1);
    return {
      ...profile,
      followed_by_viewer: followed,
      follower_count: Math.max(0, (profile.follower_count ?? 0) + followerDelta)
    };
  });

  if (state.viewedProfile?.id === profileId) {
    const currentFollowed = Boolean(state.viewedProfile.followed_by_viewer);
    const followerDelta = followed === currentFollowed ? 0 : (followed ? 1 : -1);
    state.viewedProfile = {
      ...state.viewedProfile,
      followed_by_viewer: followed,
      follower_count: Math.max(0, (state.viewedProfile.follower_count ?? 0) + followerDelta)
    };
  }

  if (state.loadedDeckOwner?.id === profileId) {
    const listed = state.profiles.find((profile) => profile.id === profileId);
    if (listed) {
      state.loadedDeckOwner = {
        ...state.loadedDeckOwner,
        followed_by_viewer: Boolean(listed.followed_by_viewer),
        follower_count: listed.follower_count ?? state.loadedDeckOwner.follower_count
      };
    }
  }

  if (state.activeProfileDetail) {
    const following = [...(state.activeProfileDetail.following || [])];
    const existingIndex = following.findIndex((profile) => profile.id === profileId);
    const targetProfile = state.profiles.find((profile) => profile.id === profileId)
      || state.viewedProfile
      || state.loadedDeckOwner;
    if (followed && existingIndex === -1 && targetProfile) {
      following.push({ id: targetProfile.id, username: targetProfile.username });
      state.activeProfileDetail = {
        ...state.activeProfileDetail,
        following,
        following_count: Math.max(0, (state.activeProfileDetail.following_count ?? 0) + 1)
      };
    } else if (!followed && existingIndex !== -1) {
      following.splice(existingIndex, 1);
      state.activeProfileDetail = {
        ...state.activeProfileDetail,
        following,
        following_count: Math.max(0, (state.activeProfileDetail.following_count ?? 0) - 1)
      };
    }
  }
}

async function toggleFollowProfile(profileId) {
  if (!state.activeProfileId) {
    setStatus("Log in first to follow profiles.", "error");
    return;
  }
  const previousProfiles = state.profiles.map((profile) => ({ ...profile }));
  const previousViewedProfile = state.viewedProfile ? { ...state.viewedProfile } : null;
  const previousLoadedDeckOwner = state.loadedDeckOwner ? { ...state.loadedDeckOwner } : null;
  const previousActiveProfileDetail = state.activeProfileDetail
    ? { ...state.activeProfileDetail, following: [...(state.activeProfileDetail.following || [])] }
    : null;
  const nextFollowed = !isProfileFollowed(profileId);

  setProfileFollowState(profileId, nextFollowed);
  renderProfile();
  renderExploreUsers();
  renderBuilder();

  try {
    await fetchJson(`${API_BASE}/profiles/${profileId}/follow`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ follower_profile_id: state.activeProfileId })
    });
  } catch (error) {
    state.profiles = previousProfiles;
    state.viewedProfile = previousViewedProfile;
    state.loadedDeckOwner = previousLoadedDeckOwner;
    state.activeProfileDetail = previousActiveProfileDetail;
    renderProfile();
    renderExploreUsers();
    renderBuilder();
    throw error;
  }

  void hydrateProfiles().then(() => {
    renderAuthNavigation();
    renderProfile();
    renderExploreUsers();
    renderBuilder();
  }).catch(() => {});
  void loadProfileDecks(state.activeProfileId).then(() => renderProfileDecks()).catch(() => {});
  void loadNotifications().then(() => renderNotifications()).catch(() => {});
  if (state.viewedProfile?.id === profileId) {
    void fetchJson(withViewer(`${API_BASE}/profiles/${profileId}`))
      .then((payload) => {
        state.viewedProfile = payload;
        renderProfile();
      })
      .catch(() => {});
  }
}

async function toggleFollowViewedProfile() {
  if (!state.viewedProfile) {
    return;
  }
  await toggleFollowProfile(state.viewedProfile.id);
}

function renderPrintDeckOptions() {
  if (!elements.printDeckSelect) {
    return;
  }
  const currentValue = elements.printDeckSelect.value || "working";
  elements.printDeckSelect.replaceChildren();

  const workingOption = document.createElement("option");
  workingOption.value = "working";
  workingOption.textContent = "Current Working Deck";
  elements.printDeckSelect.append(workingOption);

  for (const deck of state.profileDecks) {
    const option = document.createElement("option");
    option.value = deck.public_id;
    option.textContent = `${deck.title} (${deck.card_total})`;
    elements.printDeckSelect.append(option);
  }

  elements.printDeckSelect.value = [...elements.printDeckSelect.options].some((option) => option.value === currentValue)
    ? currentValue
    : "working";
}

function renderBuilderDeckOptions() {
  if (!elements.builderDeckSelect) {
    return;
  }
  const currentValue = elements.builderDeckSelect.value || "working";
  elements.builderDeckSelect.replaceChildren();

  const workingOption = document.createElement("option");
  workingOption.value = "working";
  workingOption.textContent = "Current Working Deck";
  elements.builderDeckSelect.append(workingOption);

  for (const deck of [...state.profileDecks].sort((a, b) => a.title.localeCompare(b.title))) {
    const option = document.createElement("option");
    option.value = deck.public_id;
    option.textContent = deck.title;
    elements.builderDeckSelect.append(option);
  }

  elements.builderDeckSelect.value = [...elements.builderDeckSelect.options].some((option) => option.value === currentValue)
    ? currentValue
    : "working";
}

function renderBuilderEntry() {
  if (!isBuilderLandingPage || !elements.builderEntryPanel) {
    return;
  }

  elements.builderEntryPanel.hidden = state.builderReady;
  for (const section of elements.builderEditorSections) {
    section.hidden = !state.builderReady;
  }

  if (elements.modifyDeckPanel) {
    elements.modifyDeckPanel.hidden = true;
  }
  if (elements.builderEntryStatus) {
    elements.builderEntryStatus.textContent = "";
  }
}

async function maybeLoadBuilderDeckFromQuery() {
  if (!isDeckEditorPage && !isHistoryPage) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const deckId = params.get("deck");
  if (!deckId) {
    return;
  }
  const payload = await loadDeckIntoWorkspace(deckId, { openBuilder: true });
  setStatus(`Loaded deck for editing: ${payload.title}`, "success");
}

function maybeStartNewDeckFromQuery() {
  if (!isDeckEditorPage) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  if (!params.has("new")) {
    return;
  }
  startNewDeck();
}

function maybeOpenImportedDeckFromQuery() {
  if (!isDeckEditorPage) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  if (!params.has("import")) {
    return;
  }
  state.builderReady = true;
  state.deckReadOnly = false;
  state.deckOwnerId = state.activeProfileId;
  void loadDeckHistory(state.loadedShareId).then(() => renderDeckHistory());
  renderBuilderEntry();
  renderBuilder();
  renderCards();
  renderPrintPages();
  renderHeaderStats();
  setStatus(`Opened imported deck: ${deckSnapshotTitle()}`, "success");
  window.history.replaceState({}, "", "/builder/editor");
}

async function loadDeckIntoWorkspace(publicId, options = {}) {
  const payload = await fetchJson(withViewer(`${API_BASE}/decks/${publicId}`));
  state.loadedShareId = payload.public_id;
  state.deck = Object.fromEntries(payload.cards.map((entry) => [String(entry.card.id), entry.quantity]));
  state.deckVisibility = payload.visibility === "private" ? "private" : "public";
  state.deckCoverImageUrl = payload.cover_image_url || null;
  state.loadedDeckOwner = payload.owner || null;
  state.loadedDeckLikeCount = payload.like_count || 0;
  state.loadedDeckLikedByViewer = Boolean(payload.liked_by_viewer);
  for (const entry of payload.cards) {
    state.cardIndex[String(entry.card.id)] = entry.card;
  }
  state.deckOwnerId = payload.owner?.id ?? null;
  state.deckReadOnly = !state.activeProfileId || state.deckOwnerId !== state.activeProfileId;
  if (!state.deckReadOnly && state.activeProfileId) {
    state.loadedDeckOwner = activeProfile();
  }
  if (elements.deckTitleInput) {
    elements.deckTitleInput.value = payload.title;
  }
  if (elements.deckVisibilitySelect) {
    elements.deckVisibilitySelect.value = state.deckVisibility;
  }
  if (elements.pdfExportLink) {
    elements.pdfExportLink.href = withViewer(`${API_BASE}/decks/${payload.public_id}/pdf`);
  }
  if (elements.printPdfExportLink) {
    elements.printPdfExportLink.href = withViewer(`${API_BASE}/decks/${payload.public_id}/pdf`);
  }
  if (options.openBuilder) {
    state.builderReady = true;
    state.builderModifyOpen = false;
  }
  persistDeckSnapshot();
  markDeckSaved();
  renderBuilderEntry();
  renderBuilder();
  renderCards();
  renderPrintPages();
  renderHeaderStats();
  void loadDeckHistory(payload.public_id).then(() => renderDeckHistory()).catch((error) => {
    console.warn("loadDeckHistory failed", error);
  });
  return payload;
}

function resetExportSelect() {
  if (elements.exportSelect) {
    elements.exportSelect.value = "";
  }
}

async function handleExportSelection(event) {
  const value = event.target.value;
  if (value === "png") {
    await exportViewPng();
  } else if (value === "pdf") {
    await exportPdfPrint();
  } else if (value === "text") {
    await exportDeckText();
  }
}

async function loadPrintDeckSelection(value) {
  if (!value || value === "working") {
    renderPrintPages();
    renderHeaderStats();
    setStatus("Using the current working deck for print.", "success");
    return;
  }

  const payload = await fetchJson(withViewer(`${API_BASE}/decks/${value}`));
  state.loadedShareId = payload.public_id;
  state.deck = Object.fromEntries(payload.cards.map((entry) => [String(entry.card.id), entry.quantity]));
  state.deckCoverImageUrl = payload.cover_image_url || null;
  for (const entry of payload.cards) {
    state.cardIndex[String(entry.card.id)] = entry.card;
  }
  if (elements.deckTitleInput) {
    elements.deckTitleInput.value = payload.title;
  }
  if (elements.printPdfExportLink) {
    elements.printPdfExportLink.href = withViewer(`${API_BASE}/decks/${payload.public_id}/pdf`);
  }
  persistDeckSnapshot();
  markDeckSaved();
  await loadDeckHistory(payload.public_id);
  renderBuilder();
  renderPrintPages();
  renderHeaderStats();
  setStatus(`Loaded print deck: ${payload.title}`, "success");
}

function resetDeckExportLinks() {
  if (elements.pdfExportLink) {
    elements.pdfExportLink.href = "#";
  }
  if (elements.printPdfExportLink) {
    elements.printPdfExportLink.href = "#";
  }
}

function startNewDeck(options = {}) {
  if (!state.activeProfileId) {
    setStatus("Sign up or log in first to start a new deck.", "error");
    openAuthModal();
    return;
  }
  if (isBuilderLandingPage) {
    window.location.href = "/builder/editor?new=1";
    return;
  }
  state.deck = {};
  state.loadedShareId = null;
  state.deckVisibility = "public";
  state.deckCoverImageUrl = null;
  state.deckOwnerId = state.activeProfileId;
  state.loadedDeckOwner = activeProfile();
  state.loadedDeckLikeCount = 0;
  state.loadedDeckLikedByViewer = false;
  state.deckReadOnly = false;
  state.builderReady = true;
  state.builderModifyOpen = false;
  if (elements.deckTitleInput) {
    elements.deckTitleInput.value = "Paladin's Vault Deck";
  }
  if (elements.deckVisibilitySelect) {
    elements.deckVisibilitySelect.value = state.deckVisibility;
  }
  resetDeckExportLinks();
  state.deckHistory = [];
  persistDeckSnapshot();
  markDeckSaved();
  renderBuilderEntry();
  renderBuilder();
  renderCards();
  renderPrintPages();
  renderHeaderStats();
  if (!options.preserveQuery && isDeckEditorPage) {
    window.history.replaceState({}, "", "/builder/editor");
  }
  setStatus("Started a new deck.", "success");
}

function openModifyDeckPanel() {
  state.builderModifyOpen = true;
  renderBuilderDeckOptions();
  renderBuilderEntry();
}

function closeModifyDeckPanel() {
  state.builderModifyOpen = false;
  renderBuilderEntry();
}

async function loadSelectedBuilderDeck() {
  const selected = elements.builderDeckSelect?.value || "working";
  if (selected === "working") {
    if (totalDeckCards() === 0) {
      setStatus("No current working deck is available yet.", "error");
      return;
    }
    state.builderReady = true;
    state.builderModifyOpen = false;
    renderBuilderEntry();
    renderBuilder();
    renderCards();
    renderPrintPages();
    renderHeaderStats();
    setStatus(`Loaded working deck: ${deckSnapshotTitle()}`, "success");
    return;
  }

  const payload = await loadDeckIntoWorkspace(selected, { openBuilder: true });
  setStatus(`Loaded deck for editing: ${payload.title}`, "success");
}

async function exportViewPng() {
  const cards = expandDeckCards();
  if (cards.length === 0) {
    failExportModal("No cards are available for PNG export.");
    setStatus("No cards available for PNG export.", "error");
    resetExportSelect();
    return;
  }
  openExportModal("Preparing PNG export", `Rendering ${cards.length} cards into a deck view image...`, 4);

  const cols = cards.length <= 9 ? 3 : cards.length <= 20 ? 5 : 10;
  const rows = Math.ceil(cards.length / cols);
  const cardWidth = 180;
  const cardHeight = Math.round(cardWidth * 88 / 63);
  const labelHeight = 28;
  const gap = 10;
  const padding = 12;
  const canvas = document.createElement("canvas");
  canvas.width = padding * 2 + cols * cardWidth + (cols - 1) * gap;
  canvas.height = padding * 2 + rows * (cardHeight + labelHeight) + (rows - 1) * gap;

  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#141313";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "14px 'Space Grotesk', sans-serif";

  let loadedCount = 0;
  const imagePromises = cards.map((card) => loadCardImage(card).then((result) => {
    loadedCount += 1;
    updateExportModal(
      `Loading card images for ${deckSnapshotTitle()}...`,
      8 + (loadedCount / cards.length) * 72
    );
    return result;
  }));
  const loadedImages = await Promise.all(imagePromises);

  loadedImages.forEach(({ card, image }, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const x = padding + col * (cardWidth + gap);
    const y = padding + row * (cardHeight + labelHeight + gap);

    if (image) {
      ctx.drawImage(image, x, y, cardWidth, cardHeight);
    } else {
      ctx.fillStyle = "#f3f3f3";
      ctx.fillRect(x, y, cardWidth, cardHeight);
      ctx.strokeStyle = "#1d1d1d";
      ctx.strokeRect(x, y, cardWidth, cardHeight);
    }

    ctx.fillStyle = "#f5f5f5";
    ctx.fillRect(x, y + cardHeight, cardWidth, labelHeight);
    ctx.fillStyle = "#111111";
    ctx.fillText(truncateLabel(card.name, 26), x + cardWidth / 2, y + cardHeight + labelHeight / 2);
  });

  const anchor = document.createElement("a");
  anchor.href = canvas.toDataURL("image/png");
  anchor.download = `${slugifyFilename(deckSnapshotTitle())}-view.png`;
  anchor.click();
  resetExportSelect();
  completeExportModal(`Successfully exported to ${anchor.download}`);
  setStatus(`Export completed: ${deckSnapshotTitle()} view PNG`, "success");
}

async function loadCardImage(card) {
  if (!card.image_path) {
    return { card, image: null };
  }
  const imageUrl = new URL(card.image_path, window.location.origin).toString();
  try {
    const response = await fetch(imageUrl, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(`Image request failed: ${response.status}`);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const image = new Image();
    image.decoding = "async";
    const loaded = await new Promise((resolve, reject) => {
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Image decode failed."));
      image.src = objectUrl;
    });
    URL.revokeObjectURL(objectUrl);
    return { card, image: loaded };
  } catch (error) {
    console.warn("PNG export image load failed", card.name, error);
    return { card, image: null };
  }
}

function truncateLabel(value, maxLength) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}…`;
}

function slugifyFilename(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "deck";
}

function illustrationPathFromName(name) {
  return `/assets/assets/card_illustrations/${slugifyFilename(name)}.png`;
}

function illustrationPathFromCard(card) {
  if (!card?.name) {
    return null;
  }
  return illustrationPathFromName(card.name);
}

function renderBuilder() {
  if (!elements.deckList || !elements.deckRowTemplate) {
    return;
  }
  renderDeckHistory();
  elements.deckList.replaceChildren();
  const entries = expandedDeckEntries(state.builderSort);
  syncDeckCoverOptions(entries);
  applyDeckCoverBackground();
  if (elements.builderStatsSection) {
    elements.builderStatsSection.hidden = !state.builderReady || entries.length === 0;
  }
  const showReadOnlyOwnerPanel = Boolean(state.deckReadOnly && state.loadedDeckOwner);
  if (elements.deckWorkspaceTitle) {
    elements.deckWorkspaceTitle.textContent = deckSnapshotTitle();
    elements.deckWorkspaceTitle.classList.toggle("is-read-only", state.deckReadOnly);
  }
  if (elements.deckBackgroundField) {
    elements.deckBackgroundField.hidden = showReadOnlyOwnerPanel;
  }
  if (elements.deckHistoryPanel) {
    elements.deckHistoryPanel.hidden = true;
  }
  if (elements.deckOwnerPanel) {
    elements.deckOwnerPanel.hidden = !showReadOnlyOwnerPanel;
    elements.deckOwnerPanel.style.display = showReadOnlyOwnerPanel ? "grid" : "none";
  }
  if (showReadOnlyOwnerPanel && state.loadedDeckOwner) {
    if (elements.deckOwnerName) {
      elements.deckOwnerName.textContent = displayUsername(state.loadedDeckOwner.username);
    }
    if (elements.deckOwnerMeta) {
      elements.deckOwnerMeta.textContent = `${state.loadedDeckLikeCount} like${state.loadedDeckLikeCount === 1 ? "" : "s"}`;
    }
    if (elements.deckOwnerAvatar) {
      elements.deckOwnerAvatar.textContent = "";
      setAvatarArt(elements.deckOwnerAvatar, state.loadedDeckOwner.avatar_url || DEFAULT_LOGO_URL);
      elements.deckOwnerAvatar.classList.add("profile-avatar-image");
    }
    if (elements.deckOwnerFollowButton) {
      applyFollowButtonState(elements.deckOwnerFollowButton, state.loadedDeckOwner.id);
      elements.deckOwnerFollowButton.onclick = async () => {
        if (!state.activeProfileId) {
          setStatus("Log in first to follow profiles.", "error");
          openAuthModal();
          return;
        }
        await toggleFollowProfile(state.loadedDeckOwner.id);
        renderBuilder();
      };
    }
    if (elements.deckOwnerLikeButton && state.loadedShareId) {
      elements.deckOwnerLikeButton.hidden = state.loadedDeckOwner.id === state.activeProfileId;
      elements.deckOwnerLikeButton.textContent = state.loadedDeckLikedByViewer ? "Crystal Liked" : "Crystal Like";
      elements.deckOwnerLikeButton.classList.toggle("is-liked", state.loadedDeckLikedByViewer);
      elements.deckOwnerLikeButton.onclick = async () => {
        await toggleDeckLike(state.loadedShareId);
        renderBuilder();
      };
    }
  } else {
    if (elements.deckOwnerPanel) {
      elements.deckOwnerPanel.hidden = true;
    }
    if (elements.deckOwnerFollowButton) {
      elements.deckOwnerFollowButton.onclick = null;
    }
    if (elements.deckOwnerLikeButton) {
      elements.deckOwnerLikeButton.onclick = null;
      elements.deckOwnerLikeButton.hidden = true;
    }
  }
  if (elements.clearDeckButton) {
    elements.clearDeckButton.hidden = state.deckReadOnly;
  }
  if (elements.deckVisibilitySelect) {
    elements.deckVisibilitySelect.value = state.deckVisibility;
    elements.deckVisibilitySelect.disabled = state.deckReadOnly;
  }
  if (elements.deckCoverSelect) {
    elements.deckCoverSelect.disabled = state.deckReadOnly || entries.length === 0;
  }
  elements.deckList.classList.toggle("deck-list-image-mode", state.builderView === "image");
  elements.deckList.classList.toggle("deck-list-text-mode", state.builderView !== "image");

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "Your active deck is empty. Add cards from the browser or import a text list.";
    elements.deckList.append(empty);
  }

  if (state.builderView === "image") {
    for (const entry of entries) {
      elements.deckList.append(buildDeckImageCard(entry));
    }
    renderCivilizationBreakdown(entries);
    renderManaCurve(entries);
    return;
  }

  for (const entry of entries) {
    const fragment = elements.deckRowTemplate.content.cloneNode(true);
    const row = fragment.querySelector(".deck-row");
    const rowName = fragment.querySelector(".deck-row-name");
    const rowMeta = fragment.querySelector(".deck-row-meta");
    const rowCount = fragment.querySelector(".deck-row-count");
    rowName.textContent = entry.card.name;
    rowMeta.textContent = `${entry.card.civilizations.join(" / ")} • ${entry.card.type} • ${entry.card.cost} mana`;
    rowCount.textContent = `x${entry.count}`;
    row.classList.add("is-clickable");
    row.tabIndex = 0;
    row.setAttribute("role", "link");
    row.setAttribute("aria-label", `Open ${entry.card.name} card details`);
    row.addEventListener("click", () => openCardDetail(entry.card));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCardDetail(entry.card);
      }
    });
    const incrementButton = fragment.querySelector(".increment-button");
    const decrementButton = fragment.querySelector(".decrement-button");
    incrementButton.disabled = state.deckReadOnly;
    decrementButton.disabled = state.deckReadOnly;
    incrementButton.addEventListener("click", (event) => {
      event.stopPropagation();
      addCardToDeck(entry.card.id);
    });
    decrementButton.addEventListener("click", (event) => {
      event.stopPropagation();
      removeCardFromDeck(entry.card.id);
    });
    elements.deckList.append(fragment);
  }

  renderCivilizationBreakdown(entries);
  renderManaCurve(entries);
}

function renderCards() {
  if (!elements.catalogGrid || !elements.cardTemplate) {
    return;
  }
  elements.catalogGrid.replaceChildren();
  renderSelectedSearchCard();
  renderSearchSuggestions();

  if (isDeckEditorPage && !state.filters.search) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "Start typing in the search bar to show matching cards.";
    elements.catalogGrid.append(empty);
    return;
  }

  if (state.cards.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "No cards matched the current filters.";
    elements.catalogGrid.append(empty);
    return;
  }

  for (const card of state.cards) {
    const fragment = elements.cardTemplate.content.cloneNode(true);
    const cardItem = fragment.querySelector(".card-item");
    fragment.querySelector(".card-name").textContent = card.name;
    fragment.querySelector(".card-civilization").textContent = card.civilizations.join(" / ");
    fragment.querySelector(".card-cost").textContent = `${card.cost} mana`;
    fragment.querySelector(".card-type").textContent = `${card.type} • ${card.race_label}`;
    fragment.querySelector(".card-rules").textContent = card.text;
    cardItem.classList.add("is-clickable");
    cardItem.tabIndex = 0;
    cardItem.setAttribute("role", "link");
    cardItem.setAttribute("aria-label", `Open ${card.name} card details`);
    cardItem.addEventListener("click", () => openCardDetail(card));
    cardItem.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCardDetail(card);
      }
    });
    const addButton = fragment.querySelector(".add-button");
    addButton.disabled = state.deckReadOnly;
    addButton.textContent = state.deckReadOnly ? "Read Only" : "+ Add to Deck";
    addButton.addEventListener("click", (event) => {
      event.stopPropagation();
      addCardToDeck(card.id);
    });

    const art = fragment.querySelector(".card-art");
    art.style.background = cardGradient(card.civilizations[0]);
    const previewImage = card.illustration_path || card.image_path;
    if (previewImage) {
      art.style.backgroundImage = `linear-gradient(rgba(18, 16, 14, 0.16), rgba(18, 16, 14, 0.16)), url('${previewImage}')`;
      art.style.backgroundSize = "cover";
      art.style.backgroundPosition = "center";
    }

    elements.catalogGrid.append(fragment);
  }
}

function renderPrintPages() {
  if (!elements.printPages) {
    return;
  }
  elements.printPages.replaceChildren();
  const cardsForPrint = expandDeckCards();

  if (cardsForPrint.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "No deck is available for printing yet. Build or import a deck first, then open Print.";
    elements.printPages.append(empty);
    return;
  }

  const pageSize = 9;
  for (let index = 0; index < cardsForPrint.length; index += pageSize) {
    const pageCards = cardsForPrint.slice(index, index + pageSize);
    const pageNode = document.createElement("div");
    pageNode.className = "print-page";

    for (const card of pageCards) {
      const cardNode = document.createElement("article");
      cardNode.className = "print-card";
      if (card.image_path) {
        cardNode.innerHTML = `<img src="${card.image_path}" alt="${escapeHtml(card.name)}" loading="lazy" decoding="async">`;
      } else {
        cardNode.classList.add("print-card-fallback");
        cardNode.innerHTML = `<div class="print-card-placeholder" aria-label="${escapeHtml(card.name)}"></div>`;
      }
      pageNode.append(cardNode);
    }

    elements.printPages.append(pageNode);
  }
}

function renderHeaderStats() {
  if (elements.cardCount) {
    elements.cardCount.textContent = state.cardsLoaded ? String(state.cards.length) : "0";
  }
  if (elements.deckCount) {
    elements.deckCount.textContent = String(totalDeckCards());
  }
  if (elements.averageCost) {
    elements.averageCost.textContent = averageCost().toFixed(1);
  }
}

function deriveAutomaticDeckCover() {
  const entries = expandedDeckEntries("mana");
  if (entries.length === 0) {
    return null;
  }
  const preferred = [...entries].sort((left, right) => {
    if (right.count !== left.count) return right.count - left.count;
    if ((right.card.cost || 0) !== (left.card.cost || 0)) return (right.card.cost || 0) - (left.card.cost || 0);
    return left.card.name.localeCompare(right.card.name);
  })[0];
  return preferred?.card ? illustrationPathFromCard(preferred.card) : null;
}

function syncDeckCoverOptions(entries) {
  if (!elements.deckCoverSelect) {
    return;
  }
  const select = elements.deckCoverSelect;
  const previous = state.deckCoverImageUrl || "";
  select.replaceChildren();

  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = "Auto from deck";
  select.append(autoOption);

  for (const entry of entries) {
    const illustration = illustrationPathFromCard(entry.card);
    if (!illustration) {
      continue;
    }
    const option = document.createElement("option");
    option.value = illustration;
    option.textContent = entry.card.name;
    select.append(option);
  }

  const fallback = deriveAutomaticDeckCover();
  const allowed = new Set([...select.options].map((option) => option.value));
  if (!allowed.has(previous)) {
    state.deckCoverImageUrl = fallback;
  }
  select.value = state.deckCoverImageUrl && allowed.has(state.deckCoverImageUrl) ? state.deckCoverImageUrl : "";
}

function applyDeckCoverBackground() {
  if (!elements.deckWorkspacePanel) {
    return;
  }
  const cover = state.deckCoverImageUrl || deriveAutomaticDeckCover();
  elements.deckWorkspacePanel.style.setProperty("--deck-cover-image", cover ? `url('${cover}')` : "none");
  elements.deckWorkspacePanel.classList.toggle("has-deck-cover", Boolean(cover));
}

async function loadDeckHistory(publicId) {
  if (!publicId) {
    state.deckHistory = [];
    return;
  }
  try {
    const payload = await fetchJson(withViewer(`${API_BASE}/decks/${publicId}/history`));
    state.deckHistory = payload.items ?? [];
  } catch {
    state.deckHistory = [];
  }
}

function renderDeckHistory() {
  if (!elements.deckHistoryList) {
    return;
  }
  elements.deckHistoryList.replaceChildren();
  if (elements.historyPageTitle) {
    elements.historyPageTitle.textContent = `${deckSnapshotTitle()} History`;
  }
  if (elements.historyPageSubtitle) {
    elements.historyPageSubtitle.textContent = state.loadedShareId
      ? "Review the saved change log for this deck."
      : "This working deck has not been saved yet, so there is no revision history to display.";
  }

  if (!state.loadedShareId) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "This deck will start building a history as soon as it is saved to your profile.";
    elements.deckHistoryList.append(empty);
    return;
  }

  if (state.deckHistory.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hero-text";
    empty.textContent = "No tracked changes yet for this deck.";
    elements.deckHistoryList.append(empty);
    return;
  }

  for (const entry of state.deckHistory) {
    const article = document.createElement("article");
    article.className = "deck-history-item";
    const isAdded = entry.change_type === "added";
    article.innerHTML = `
      <div class="deck-history-topline">
        <strong class="deck-history-symbol ${isAdded ? "is-added" : "is-removed"}">${isAdded ? "+" : "-"}</strong>
        <span>${escapeHtml(entry.created_at_label)}</span>
      </div>
      <p class="deck-history-note">${escapeHtml(entry.card_name)}</p>
    `;
    elements.deckHistoryList.append(article);
  }
}

function buildDeckImageCard(entry) {
  const article = document.createElement("article");
  article.className = "deck-image-card";
  article.classList.add("is-clickable");
  article.tabIndex = 0;
  article.setAttribute("role", "link");
  article.setAttribute("aria-label", `Open ${entry.card.name} card details`);
  article.addEventListener("click", () => openCardDetail(entry.card));
  article.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openCardDetail(entry.card);
    }
  });

  const art = document.createElement("div");
  art.className = "deck-image-art";
  art.style.background = cardGradient(entry.card.civilizations[0]);
  if (entry.card.image_path) {
    const cardImage = document.createElement("img");
    cardImage.src = entry.card.image_path;
    cardImage.alt = entry.card.name;
    cardImage.loading = "lazy";
    cardImage.decoding = "async";
    art.append(cardImage);
  }

  const quantity = document.createElement("span");
  quantity.className = "deck-image-quantity";
  quantity.textContent = `x${entry.count}`;

  const meta = document.createElement("div");
  meta.className = "deck-image-meta";
  meta.innerHTML = `
    <strong>${escapeHtml(entry.card.name)}</strong>
    <span>${escapeHtml(entry.card.civilizations.join(" / "))} • ${escapeHtml(entry.card.type)}</span>
    <small>${entry.card.cost} mana</small>
  `;

  const actions = document.createElement("div");
  actions.className = "deck-image-actions";

  const decrement = document.createElement("button");
  decrement.type = "button";
  decrement.className = "small-button decrement-button";
  decrement.textContent = "-";
  decrement.disabled = state.deckReadOnly;
  decrement.addEventListener("click", (event) => {
    event.stopPropagation();
    removeCardFromDeck(entry.card.id);
  });

  const increment = document.createElement("button");
  increment.type = "button";
  increment.className = "small-button increment-button";
  increment.textContent = "+";
  increment.disabled = state.deckReadOnly;
  increment.addEventListener("click", (event) => {
    event.stopPropagation();
    addCardToDeck(entry.card.id);
  });

  actions.append(decrement, increment);
  article.append(art, quantity, meta, actions);
  return article;
}

function renderCivilizationBreakdown(entries) {
  if (!elements.civilizationBreakdown) {
    return;
  }
  elements.civilizationBreakdown.replaceChildren();
  const counts = new Map();

  for (const entry of entries) {
    for (const civ of entry.card.civilizations) {
      counts.set(civ, (counts.get(civ) ?? 0) + entry.count);
    }
  }

  for (const [civ, count] of counts.entries()) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = `${civ}: ${count}`;
    elements.civilizationBreakdown.append(chip);
  }
}

function renderManaCurve(entries) {
  if (!elements.manaCurve) {
    return;
  }
  elements.manaCurve.replaceChildren();
  const curve = new Map();
  for (let cost = 1; cost <= 14; cost += 1) {
    curve.set(cost, 0);
  }
  for (const entry of entries) {
    curve.set(entry.card.cost, (curve.get(entry.card.cost) ?? 0) + entry.count);
  }
  const peak = Math.max(...curve.values(), 1);

  for (const [cost, count] of curve.entries()) {
    const wrapper = document.createElement("div");
    wrapper.className = "curve-bar";

    const countLabel = document.createElement("small");
    countLabel.textContent = String(count);
    const fill = document.createElement("div");
    fill.className = "curve-bar-fill";
    fill.style.height = `${Math.max((count / peak) * 110, 8)}px`;
    const costLabel = document.createElement("small");
    costLabel.textContent = String(cost);

    wrapper.append(countLabel, fill, costLabel);
    elements.manaCurve.append(wrapper);
  }
}

function addCardToDeck(cardId) {
  if (state.deckReadOnly) {
    setStatus("This deck is read-only. Duplicate it to your profile to edit it.", "error");
    return;
  }
  state.deck[String(cardId)] = (state.deck[String(cardId)] ?? 0) + 1;
  persistDeckSnapshot();
  const card = state.cardIndex[String(cardId)];
  markDeckDirty(card ? `Added ${card.name}` : "Added card");
  renderBuilder();
  renderPrintPages();
  renderHeaderStats();
  if (card) {
    setStatus(`${card.name} added.`, "success");
  }
}

function removeCardFromDeck(cardId) {
  if (state.deckReadOnly) {
    setStatus("This deck is read-only. Duplicate it to your profile to edit it.", "error");
    return;
  }
  const key = String(cardId);
  if (!state.deck[key]) {
    return;
  }
  state.deck[key] -= 1;
  if (state.deck[key] <= 0) {
    delete state.deck[key];
  }
  persistDeckSnapshot();
  const card = state.cardIndex[key];
  markDeckDirty(card ? `Removed ${card.name}` : "Removed card");
  renderBuilder();
  renderPrintPages();
  renderHeaderStats();
}

async function importTextDeck() {
  const raw = elements.textImportInput?.value.trim() ?? "";
  if (!raw) {
    setTextImportStatus("Paste a decklist first.", "error");
    return;
  }

  await loadAllCards();
  const nextDeck = {};
  const missing = [];
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);

  for (const line of lines) {
    const match = line.match(/^(\d+)\s+(.+)$/);
    const quantity = match ? Number(match[1]) : 1;
    const name = match ? match[2] : line;
    const card = resolveCardByText(name);
    if (!card) {
      missing.push(name);
      continue;
    }
    nextDeck[String(card.id)] = (nextDeck[String(card.id)] ?? 0) + quantity;
  }

  state.deck = nextDeck;
  state.loadedShareId = null;
  state.deckVisibility = "public";
  state.deckCoverImageUrl = null;
  state.deckReadOnly = false;
  state.deckOwnerId = state.activeProfileId;
  if (elements.deckVisibilitySelect) {
    elements.deckVisibilitySelect.value = state.deckVisibility;
  }
  await hydrateDeckCards();
  state.deckDirtyToken += 1;
  state.hasUnsavedProfileChanges = true;
  state.pendingChangeNote = "Imported decklist";
  persistDeckSnapshot();
  renderBuilder();
  renderPrintPages();
  renderHeaderStats();

  if (missing.length > 0) {
    setTextImportStatus(`Import completed: ${deckSnapshotTitle()} • Missing: ${missing.join(", ")}`, "success");
  } else {
    setTextImportStatus(`Import completed: ${deckSnapshotTitle()}`, "success");
  }
  if (state.activeProfileId) {
    const savedDeck = await saveDeckToProfile({ silent: true, autosave: true });
    if (savedDeck?.public_id) {
      window.location.assign(`/builder/editor?deck=${encodeURIComponent(savedDeck.public_id)}`);
      return;
    }
  }
  window.location.assign("/builder/editor?import=1");
}

function resolveCardByText(input) {
  const normalized = normalizeName(input);
  const exact = state.allCards.find((card) => normalizeName(card.name) === normalized);
  if (exact) {
    return exact;
  }
  const startsWith = state.allCards.find((card) => normalizeName(card.name).startsWith(normalized));
  if (startsWith) {
    return startsWith;
  }
  const contains = state.allCards.find((card) => normalizeName(card.name).includes(normalized));
  if (contains) {
    return contains;
  }

  let best = null;
  let bestScore = Number.POSITIVE_INFINITY;
  for (const card of state.allCards) {
    const score = levenshtein(normalized, normalizeName(card.name));
    if (score < bestScore) {
      bestScore = score;
      best = card;
    }
  }
  return bestScore <= 3 ? best : null;
}

function normalizeName(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

async function exportDeckText() {
  const entries = expandedDeckEntries();
  if (entries.length === 0) {
    failExportModal("No cards are available for text export.");
    setStatus("No cards available for text export.", "error");
    resetExportSelect();
    return;
  }
  openExportModal("Preparing text export", "Building your decklist text file...", 35);
  const body = entries.map((entry) => `${entry.count} ${entry.card.name}`).join("\n");
  const blob = new Blob([`${deckSnapshotTitle()}\n\n${body}\n`], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${slugifyFilename(deckSnapshotTitle())}.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
  resetExportSelect();
  completeExportModal(`Successfully exported to ${anchor.download}`);
  setStatus(`Export completed: ${deckSnapshotTitle()} text`, "success");
}

async function exportPdfPrint() {
  if (!state.loadedShareId) {
    failExportModal("This deck must be synced before PDF export.");
    setStatus("This deck needs to sync once before exporting a PDF print file.", "error");
    resetExportSelect();
    return;
  }
  const filename = `${slugifyFilename(deckSnapshotTitle())}.pdf`;
  openExportModal("Preparing PDF export", `Generating printable PDF for ${deckSnapshotTitle()}...`, 10);
  try {
    updateExportModal("Generating printable deck sheets on the server...", 28);
    const blob = await fetchBlobWithProgress(
      withViewer(`${API_BASE}/decks/${state.loadedShareId}/pdf`),
      {
        startPercent: 34,
        endPercent: 94,
        progressMessage: `Downloading ${filename}...`
      }
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    resetExportSelect();
    completeExportModal(`Successfully exported to ${filename}`);
    setStatus(`Export completed: ${deckSnapshotTitle()} PDF`, "success");
  } catch (error) {
    failExportModal(error.message || "PDF export failed.");
    setStatus(error.message || "PDF export failed.", "error");
    resetExportSelect();
  }
}

function importDeckJson(event) {
  const [file] = event.target.files ?? [];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    try {
      const payload = JSON.parse(String(reader.result));
      state.deck = Object.fromEntries((payload.cards ?? [])
        .filter((entry) => Number(entry.quantity) > 0)
        .map((entry) => [String(entry.cardId), Number(entry.quantity)]));
      if (payload.title && elements.deckTitleInput) {
        elements.deckTitleInput.value = payload.title;
      }
      hydrateDeckCards().then(() => {
        persistDeckSnapshot();
        markDeckDirty("Imported JSON deck");
        renderBuilder();
        renderPrintPages();
        renderHeaderStats();
        setStatus(`Import completed: ${payload.title || deckSnapshotTitle()}`, "success");
      });
    } catch {
      setStatus("Invalid JSON deck file.", "error");
    } finally {
      event.target.value = "";
    }
  };
  reader.readAsText(file);
}

async function saveDeckToProfile(options = {}) {
  const { silent = false, autosave = false } = options;
  if (state.deckReadOnly) {
    return duplicateCurrentDeckToProfile();
  }
  if (state.autosaveInFlight) {
    if (autosave) {
      state.autosaveQueued = true;
      return null;
    }
    setStatus("A save is already in progress.", "info");
    return null;
  }
  const title = elements.deckTitleInput?.value.trim() || "Paladin's Vault Deck";
  const cards = Object.entries(state.deck).map(([cardId, quantity]) => ({
    card_id: Number(cardId),
    quantity
  }));

  if (!state.activeProfileId) {
    if (!silent) {
      setStatus("Register a profile before saving decks.", "error");
    }
    return null;
  }

  const requestToken = state.deckDirtyToken;
  state.autosaveInFlight = true;
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/decks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        public_id: state.loadedShareId,
        title,
        visibility: state.deckVisibility,
        cover_image_url: state.deckCoverImageUrl || deriveAutomaticDeckCover(),
        profile_id: state.activeProfileId,
        change_note: state.pendingChangeNote,
        cards
      })
    });
  } catch {
    state.autosaveInFlight = false;
    if (!silent) {
      setStatus("Saving to profile failed. Make sure the profile exists and the deck contains valid cards.", "error");
    }
    return null;
  }
  state.autosaveInFlight = false;

  state.loadedShareId = payload.public_id;
  state.deckVisibility = payload.visibility === "private" ? "private" : "public";
  state.deckCoverImageUrl = payload.cover_image_url || state.deckCoverImageUrl || deriveAutomaticDeckCover();
  state.deckOwnerId = state.activeProfileId;
  state.loadedDeckOwner = activeProfile();
  state.loadedDeckLikeCount = 0;
  state.loadedDeckLikedByViewer = false;
  state.deckReadOnly = false;
  if (elements.deckVisibilitySelect) {
    elements.deckVisibilitySelect.value = state.deckVisibility;
  }
  if (elements.pdfExportLink) {
    elements.pdfExportLink.href = withViewer(`${API_BASE}/decks/${payload.public_id}/pdf`);
  }
  if (elements.printPdfExportLink) {
    elements.printPdfExportLink.href = withViewer(`${API_BASE}/decks/${payload.public_id}/pdf`);
  }
  await loadProfileDecks(state.activeProfileId);
  if (needsExploreDecks(page)) {
    await loadExploreDecks();
    renderExploreDecks();
  }
  await loadDeckHistory(payload.public_id);
  renderProfile();
  renderProfileDecks();
  persistDeckSnapshot();
  if (state.deckDirtyToken === requestToken) {
    markDeckSaved();
  } else {
    state.autosaveQueued = false;
    scheduleDeckAutosave();
  }
  if (state.autosaveQueued && state.hasUnsavedProfileChanges) {
    state.autosaveQueued = false;
    scheduleDeckAutosave();
  }
  if (!silent) {
    setStatus("Deck saved.", "success");
  }
  return payload;
}

async function duplicateDeckToProfile(publicId) {
  if (!state.activeProfileId) {
    setStatus("Log in first to duplicate decks.", "error");
    return null;
  }
  const payload = await fetchJson(withViewer(`${API_BASE}/decks/${publicId}`));
  const duplicateTitle = uniqueDuplicateTitle(payload.title);
  const cards = payload.cards.map((entry) => ({
    card_id: entry.card.id,
    quantity: entry.quantity
  }));

  const duplicate = await fetchJson(`${API_BASE}/decks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: duplicateTitle,
      visibility: "private",
      profile_id: state.activeProfileId,
      change_note: "Duplicated deck",
      cards
    })
  });

  await loadProfileDecks(state.activeProfileId);
  if (needsExploreDecks(page)) {
    await loadExploreDecks();
    renderExploreDecks();
  }
  renderProfileDecks();
  setStatus(`Duplicated to My Decks: ${duplicate.title}`, "success");
  return duplicate;
}

async function duplicateCurrentDeckToProfile() {
  if (!state.loadedShareId) {
    setStatus("No deck is loaded to duplicate.", "error");
    return null;
  }
  const duplicate = await duplicateDeckToProfile(state.loadedShareId);
  if (!duplicate) {
    return null;
  }
  const payload = await loadDeckIntoWorkspace(duplicate.public_id, { openBuilder: true });
  state.deckReadOnly = false;
  state.deckOwnerId = state.activeProfileId;
  state.loadedDeckOwner = null;
  renderBuilder();
  renderCards();
  renderPrintPages();
  renderHeaderStats();
  setStatus(`Duplicated and opened for editing: ${payload.title}`, "success");
  return payload;
}

async function copyShareLink() {
  if (!state.loadedShareId) {
    setStatus("Save the deck first to generate a share link.", "error");
    return;
  }
  const shareUrl = new URL(`/share/${state.loadedShareId}`, window.location.origin).toString();
  await navigator.clipboard.writeText(shareUrl);
  setStatus("Share link copied.", "success");
}

async function createProfile() {
  const username = elements.newProfileName?.value.trim() ?? "";
  const displayName = username;
  const email = elements.registerEmail?.value.trim() ?? "";
  const avatarUrl = elements.registerAvatarUrl?.value.trim() ?? "";
  const password = elements.registerPassword?.value ?? "";
  if (!username || !email || !password) {
    setAuthModalStatus("Enter username, email, and password.", "error", null, "signup");
    setStatus("Enter username, email, and password.", "error");
    return;
  }

  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, username, email, avatar_url: avatarUrl || null, password })
    });
  } catch (error) {
    setAuthModalStatus(error.message || "Profile creation failed. Try another handle.", "error", null, "signup");
    setStatus(error.message || "Profile creation failed. Try another handle.", "error");
    return;
  }

  await hydrateProfiles();
  if (elements.newProfileName) elements.newProfileName.value = "";
  if (elements.registerEmail) elements.registerEmail.value = "";
  if (elements.registerAvatarUrl) elements.registerAvatarUrl.value = "";
  if (elements.registerPassword) elements.registerPassword.value = "";
  if (elements.loginEmail) elements.loginEmail.value = email;
  closeSignupModal();
  closeAuthModal();
  renderWelcome();
  renderAuthNavigation();
  renderProfile();
  renderProfileDecks();
  renderAvatarPresetChoosers();
  setAuthModalStatus(
    payload.message || "Account created. Check your email to verify your account before logging in.",
    payload.verification_email_sent ? "success" : "error",
    payload.verification_url ? { label: "Verify now", href: payload.verification_url } : null,
    "signup"
  );
  setStatus(
    payload.message || "Account created. Check your email to verify your account before logging in.",
    payload.verification_email_sent ? "success" : "error",
    payload.verification_url ? { label: "Verify now", href: payload.verification_url } : null
  );
}

async function loginProfile() {
  const email = elements.loginEmail?.value.trim() ?? "";
  const password = elements.loginPassword?.value ?? "";
  if (!email || !password) {
    setAuthModalStatus("Enter your email and password.", "error", null, "login");
    setStatus("Enter your email and password.", "error");
    return;
  }
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
  } catch (error) {
    const shouldShowResend = /verify|verification|verified/i.test(error.message || "");
    setLoginModalAuxActions(shouldShowResend);
    setAuthModalStatus(error.message || "Login failed.", "error", null, "login");
    setStatus(error.message || "Login failed.", "error");
    return;
  }
  state.activeProfileId = payload.profile.id;
  window.localStorage.setItem(PROFILE_STORAGE_KEY, String(payload.profile.id));
  await hydrateProfiles();
  persistActiveProfileCache();
  await loadNotifications();
  if (elements.loginEmail) elements.loginEmail.value = "";
  if (elements.loginPassword) elements.loginPassword.value = "";
  await loadProfileDecks(payload.profile.id);
  if (page === "admin" && payload.profile.is_admin) {
    await loadAdminOverview();
  }
  closeAuthModal();
  setLoginModalAuxActions(false);
  renderWelcome();
  renderAuthNavigation();
  renderNotifications();
  renderProfile();
  renderProfileDecks();
  renderAdminPage();
  setAuthModalStatus(`Logged in as ${displayUsername(payload.profile.username)}`, "success", null, "login");
  setStatus(`Logged in as ${displayUsername(payload.profile.username)}`, "success");
}

async function resendVerificationEmail() {
  const email = elements.loginEmail?.value.trim() || elements.registerEmail?.value.trim() || "";
  if (!email) {
    setLoginModalAuxActions(true);
    setAuthModalStatus("Enter your email first, then resend verification.", "error", null, "login");
    setStatus("Enter your email first, then resend verification.", "error");
    return;
  }
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/auth/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
  } catch (error) {
    setLoginModalAuxActions(true);
    setAuthModalStatus(error.message || "Verification email resend failed.", "error", null, "login");
    setStatus(error.message || "Verification email resend failed.", "error");
    return;
  }
  setLoginModalAuxActions(true);
  const level = payload.status === "error" ? "error" : "success";
  setAuthModalStatus(
    payload.message || "If the account exists, a verification email has been sent.",
    level,
    payload.verification_url ? { label: "Verify now", href: payload.verification_url } : null,
    "login"
  );
  setStatus(
    payload.message || "If the account exists, a verification email has been sent.",
    level,
    payload.verification_url ? { label: "Verify now", href: payload.verification_url } : null
  );
}

function logoutProfile() {
  state.hasUnsavedProfileChanges = false;
  state.autosaveInFlight = false;
  state.autosaveQueued = false;
  state.pendingChangeNote = null;
  state.activeProfileId = null;
  state.notifications = [];
  state.activeProfileDetail = null;
  state.adminOverview = null;
  state.profileDecks = [];
  state.deckReadOnly = Boolean(state.deckOwnerId);
  window.localStorage.removeItem(PROFILE_STORAGE_KEY);
  window.localStorage.removeItem(PROFILE_CACHE_KEY);
  renderBuilderDeckOptions();
  renderBuilderEntry();
  renderWelcome();
  renderAuthNavigation();
  renderNotifications();
  renderProfile();
  renderProfileDecks();
  renderAdminPage();
  setStatus("Logged out.", "success");
}

async function saveProfileUsername() {
  if (!state.activeProfileId) {
    setStatus("Log in first to change your username.", "error");
    return;
  }
  const nextUsername = elements.profileUsernameInput?.value.trim() ?? "";
  if (!nextUsername) {
    setStatus("Enter a username first.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/profiles/${state.activeProfileId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: nextUsername })
    });
    state.profiles = state.profiles.map((profile) => profile.id === payload.id ? payload : profile);
    await hydrateProfiles();
    persistActiveProfileCache();
    await loadProfileDecks(state.activeProfileId);
    if (state.viewedProfile?.id === state.activeProfileId) {
      state.viewedProfile = await fetchJson(withViewer(`${API_BASE}/profiles/${state.activeProfileId}`));
    }
    renderAuthNavigation();
    renderProfile();
    renderProfileDecks();
    setStatus(`Username updated to ${displayUsername(payload.username)}.`, "success");
  } catch (error) {
    setStatus(error.message || "Username update failed.", "error");
  }
}

async function sendAdminNotification() {
  if (!state.activeProfileId || !activeProfile()?.is_admin) {
    setStatus("Admin access is required.", "error");
    return;
  }
  const message = elements.adminNotifyMessage?.value.trim() ?? "";
  const target = Number(elements.adminNotifyTarget?.value || 0) || null;
  if (!message) {
    setStatus("Enter an admin notification message first.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/admin/notify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_profile_id: state.activeProfileId,
        target_profile_id: target,
        message
      })
    });
    if (elements.adminNotifyMessage) {
      elements.adminNotifyMessage.value = "";
    }
    setStatus(payload.message || "Notification sent.", "success");
    await loadAdminOverview();
    renderAdminPage();
  } catch (error) {
    setStatus(error.message || "Admin notification failed.", "error");
  }
}

async function sendAdminEmail() {
  if (!state.activeProfileId || !activeProfile()?.is_admin) {
    setStatus("Admin account required.", "error");
    return;
  }
  const target = Number(elements.adminEmailTarget?.value || 0);
  const manualEmail = elements.adminEmailManual?.value.trim() ?? "";
  const subject = elements.adminEmailSubject?.value.trim() ?? "";
  const message = elements.adminEmailMessage?.value.trim() ?? "";
  if (!target && !manualEmail) {
    setStatus("Choose a user or enter an email address manually.", "error");
    return;
  }
  if (!subject || !message) {
    setStatus("Enter both an email subject and message.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/admin/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_profile_id: state.activeProfileId,
        target_profile_id: target || null,
        target_email: manualEmail || null,
        subject,
        message
      })
    });
    if (elements.adminEmailTarget) {
      elements.adminEmailTarget.value = "";
    }
    if (elements.adminEmailManual) {
      elements.adminEmailManual.value = "";
    }
    if (elements.adminEmailSubject) {
      elements.adminEmailSubject.value = "";
    }
    if (elements.adminEmailMessage) {
      elements.adminEmailMessage.value = "";
    }
    setStatus(payload.message || "Admin email sent.", "success");
    await loadAdminOverview();
    renderAdminPage();
  } catch (error) {
    setStatus(error.message || "Admin email sending failed.", "error");
    await loadAdminOverview();
    renderAdminPage();
  }
}

async function verifyAdminUser(profileId) {
  if (!state.activeProfileId || !activeProfile()?.is_admin) {
    setStatus("Admin access is required.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/admin/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_profile_id: state.activeProfileId,
        target_profile_id: profileId
      })
    });
    setStatus(payload.message || "User verified.", "success");
    await hydrateProfiles();
    await loadAdminOverview();
    renderAuthNavigation();
    renderAdminPage();
  } catch (error) {
    setStatus(error.message || "Verification update failed.", "error");
  }
}

async function toggleAdminBan(profileId, banned, reason = "") {
  if (!state.activeProfileId || !activeProfile()?.is_admin) {
    setStatus("Admin access is required.", "error");
    return;
  }
  try {
    const payload = await fetchJson(`${API_BASE}/admin/ban`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_profile_id: state.activeProfileId,
        target_profile_id: profileId,
        banned,
        reason: reason || null
      })
    });
    setStatus(payload.message || "Moderation updated.", "success");
    await hydrateProfiles();
    await loadAdminOverview();
    renderAuthNavigation();
    renderAdminPage();
  } catch (error) {
    setStatus(error.message || "Moderation action failed.", "error");
  }
}

async function saveProfileAvatar(nextAvatarUrl = null, options = {}) {
  const { silent = false } = options;
  if (!state.activeProfileId) {
    if (!silent) {
      setStatus("Log in first to update your profile image.", "error");
    }
    return;
  }
  const avatarUrl = typeof nextAvatarUrl === "string" || nextAvatarUrl === null
    ? nextAvatarUrl
    : (elements.profileAvatarUrlInput?.value.trim() || null);
  let payload;
  try {
    payload = await fetchJson(`${API_BASE}/profiles/${state.activeProfileId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avatar_url: avatarUrl })
    });
  } catch (error) {
    if (!silent) {
      setStatus(error.message || "Profile image update failed.", "error");
    }
    return;
  }
  if (elements.profileAvatarUrlInput) {
    elements.profileAvatarUrlInput.value = payload.avatar_url || "";
  }
  persistActiveProfileCache();
  applyLocalAvatarUpdate(payload.avatar_url || null);
  if (!silent) {
    setStatus("Profile image saved.", "success");
  }
}

function persistDeckSnapshot() {
  const payload = {
    title: elements.deckTitleInput?.value.trim() || "Paladin's Vault Deck",
    visibility: state.deckVisibility,
    coverImageUrl: state.deckCoverImageUrl,
    deck: state.deck,
    shareId: state.loadedShareId,
    dirty: state.hasUnsavedProfileChanges
  };
  window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(payload));
}

function deckSnapshotTitle() {
  return elements.deckTitleInput?.value.trim() || "Paladin's Vault Deck";
}

function activeProfile() {
  return state.profiles.find((profile) => profile.id === state.activeProfileId) ?? cachedActiveProfile();
}

function cachedActiveProfile() {
  try {
    const raw = window.localStorage.getItem(PROFILE_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return parsed?.id ? parsed : null;
  } catch {
    return null;
  }
}

function primeCachedProfileState() {
  const storedId = Number(window.localStorage.getItem(PROFILE_STORAGE_KEY));
  if (storedId && !state.activeProfileId) {
    state.activeProfileId = storedId;
  }
}

function persistActiveProfileCache() {
  const profile = state.profiles.find((item) => item.id === state.activeProfileId);
  if (!profile) {
    window.localStorage.removeItem(PROFILE_CACHE_KEY);
    return;
  }
  window.localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify({
    id: profile.id,
    username: profile.username,
    display_name: profile.display_name,
    avatar_url: profile.avatar_url || null,
    email_verified: Boolean(profile.email_verified),
    email: profile.email || "",
    is_admin: Boolean(profile.is_admin),
    bio: profile.bio || "",
    follower_count: profile.follower_count ?? 0,
    following_count: profile.following_count ?? 0
  }));
}

function uniqueDuplicateTitle(baseTitle) {
  const existingTitles = new Set(state.profileDecks.map((deck) => normalizeName(deck.title)));
  let nextTitle = `${baseTitle} Duplicate`;
  let index = 2;
  while (existingTitles.has(normalizeName(nextTitle))) {
    nextTitle = `${baseTitle} Duplicate ${index}`;
    index += 1;
  }
  return nextTitle;
}

function totalDeckCards() {
  return Object.values(state.deck).reduce((sum, count) => sum + count, 0);
}

function averageCost() {
  const entries = expandedDeckEntries(state.builderSort);
  if (entries.length === 0) {
    return 0;
  }
  let weighted = 0;
  let count = 0;
  for (const entry of entries) {
    weighted += entry.card.cost * entry.count;
    count += entry.count;
  }
  return count === 0 ? 0 : weighted / count;
}

function expandedDeckEntries(sortMode = "mana") {
  const entries = Object.entries(state.deck)
    .filter(([, count]) => count > 0)
    .map(([cardId, count]) => ({ card: state.cardIndex[cardId], count }))
    .filter((entry) => entry.card)
  if (sortMode === "civilization") {
    return entries.sort((left, right) => {
      const leftCivilization = left.card.civilizations.join(" / ");
      const rightCivilization = right.card.civilizations.join(" / ");
      return leftCivilization.localeCompare(rightCivilization)
        || left.card.cost - right.card.cost
        || left.card.name.localeCompare(right.card.name);
    });
  }
  return entries.sort((left, right) => left.card.cost - right.card.cost || left.card.name.localeCompare(right.card.name));
}

function expandDeckCards() {
  const result = [];
  for (const entry of expandedDeckEntries()) {
    for (let index = 0; index < entry.count; index += 1) {
      result.push(entry.card);
    }
  }
  return result;
}

function initials(value) {
  return value.split(/\s+/).slice(0, 2).map((chunk) => chunk[0]?.toUpperCase() ?? "").join("") || "CV";
}

function levenshtein(left, right) {
  const rows = Array.from({ length: left.length + 1 }, () => Array(right.length + 1).fill(0));
  for (let i = 0; i <= left.length; i += 1) rows[i][0] = i;
  for (let j = 0; j <= right.length; j += 1) rows[0][j] = j;
  for (let i = 1; i <= left.length; i += 1) {
    for (let j = 1; j <= right.length; j += 1) {
      const cost = left[i - 1] === right[j - 1] ? 0 : 1;
      rows[i][j] = Math.min(
        rows[i - 1][j] + 1,
        rows[i][j - 1] + 1,
        rows[i - 1][j - 1] + cost
      );
    }
  }
  return rows[left.length][right.length];
}

function needsCards(currentPage) {
  return ["deck-editor", "cards"].includes(currentPage);
}

function needsProfileDecks(currentPage) {
  return ["profile", "my-decks", "welcome", "print", "playmode"].includes(currentPage);
}

function needsExploreDecks(currentPage) {
  return currentPage === "explore-decks";
}

function setStatus(message, type = "info", action = null) {
  for (const node of elements.statusNodes) {
    node.replaceChildren();
    if (message) {
      node.append(document.createTextNode(message));
    }
    if (action?.href && action?.label) {
      node.append(document.createTextNode(" "));
      const link = document.createElement("a");
      link.href = action.href;
      link.textContent = action.label;
      link.className = "status-action-link";
      node.append(link);
    }
    node.classList.remove("status-success", "status-error");
    if (type === "success") node.classList.add("status-success");
    if (type === "error") node.classList.add("status-error");
  }
}

function setTextImportStatus(message, type = "info") {
  if (elements.textImportStatus) {
    elements.textImportStatus.textContent = message;
    elements.textImportStatus.classList.remove("status-success", "status-error");
    if (type === "success") elements.textImportStatus.classList.add("status-success");
    if (type === "error") elements.textImportStatus.classList.add("status-error");
  } else {
    setStatus(message, type);
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return response.json();
}

function cardGradient(civilization) {
  const gradients = {
    Fire: "linear-gradient(135deg, rgba(181, 71, 47, 0.92), rgba(255, 166, 88, 0.72))",
    Water: "linear-gradient(135deg, rgba(77, 127, 155, 0.95), rgba(124, 196, 221, 0.72))",
    Darkness: "linear-gradient(135deg, rgba(64, 43, 82, 0.96), rgba(145, 73, 115, 0.74))",
    Light: "linear-gradient(135deg, rgba(201, 180, 92, 0.9), rgba(255, 242, 176, 0.72))",
    Nature: "linear-gradient(135deg, rgba(54, 95, 72, 0.95), rgba(143, 194, 121, 0.72))"
  };
  return gradients[civilization] ?? "linear-gradient(135deg, rgba(90, 90, 90, 0.9), rgba(200, 200, 200, 0.7))";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}
