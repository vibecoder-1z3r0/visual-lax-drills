// Shared constants. Field units are yards. The origin is the top-left corner of the half field and
// y grows toward midfield, so the end line is at the top and the net opens downward.
export const FIELD_W = 60;
export const FIELD_H = 55;
export const MARGIN = 3;
export const GOAL_X = 30;
export const GOAL_Y = 15;
export const CREASE_R = 3;

// Icon width in yards. Every icon is a square symbol centered on the origin. Players, balls and
// cones are drawn about twice real size (a player is about 0.7 yards across, a ball about 0.08) so
// they stay readable; drills zoom in on the action with `view` so they still look big enough.
export const ICON_SIZE = {
  player: 1.8,
  goalie: 1.9,
  coach: 1.9,
  ball: 0.7,
  cone: 0.9,
  ballbag: 1.5,
  net: 2.7,
};

// Back to front. Later kinds draw on top of earlier ones.
export const DRAW_ORDER = ["ballbag", "cone", "coach", "player", "goalie", "ball"];

export const THEMES = [
  { id: "day", name: "Day" },
  { id: "night", name: "Night" },
  { id: "stadium", name: "Stadium" },
  { id: "stage", name: "Stage" },
  { id: "bright", name: "Bright" },
  { id: "field", name: "Field" },
];

// Where the chosen theme is remembered between visits.
export const THEME_KEY = "vldTheme";

export const SPEEDS = [0.25, 0.5, 1, 1.5, 2];
