// Shared constants. Field units are yards. The origin is the top-left corner of the half field and
// y grows toward midfield, so the end line is at the top and the net opens downward.
export const FIELD_W = 60;
export const FIELD_H = 55;
export const MARGIN = 3;
export const GOAL_X = 30;
export const GOAL_Y = 15;
export const CREASE_R = 3;

// Icon width in yards. Every icon is a square symbol centered on the origin.
export const ICON_SIZE = {
  player: 3.4,
  goalie: 3.6,
  coach: 3.6,
  ball: 1.3,
  cone: 1.6,
  ballbag: 2.8,
  net: 2.7,
};

// Back to front. Later kinds draw on top of earlier ones.
export const DRAW_ORDER = ["ballbag", "cone", "coach", "player", "goalie", "ball"];

export const THEMES = [
  { id: "day", name: "Day" },
  { id: "night", name: "Night" },
  { id: "stadium", name: "Stadium" },
  { id: "field", name: "Field" },
];

// Where the chosen theme is remembered between visits.
export const THEME_KEY = "vldTheme";

export const SPEEDS = [0.25, 0.5, 1, 1.5, 2];
