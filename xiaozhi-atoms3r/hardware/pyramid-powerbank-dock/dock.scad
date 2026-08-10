// Echo Pyramid dock v7
// - Vertical power-bank bay on the SIDE
// - Pyramid chamber walls INTEGRAL, thicker walls + step seat
// - Flat plate lid: slightly smaller, rests on the step (no magnets)
// - Small pry opening at front to lift the lid
// - Full bottom passage platform <-> bay
//
// part = "base" | "lid" | "assembly"

part = "assembly";

/* ===== measured power bank ===== */
pb_l = 99.8;
pb_w = 66.6;
pb_t = 9.2;
pb_clear = 1.2;   // per-side gap for FDM + easy slide-in (was 0.8)

/* ===== Pyramid + Atom ===== */
pyramid_xy = 83.6;     // measured Pyramid outer (reference)
pyramid_clear = 0.7;   // unused when chamber_inner is set explicitly
post_h = 0;            // no internal posts — Pyramid sits on chamber floor
post_size = 8.0;
stack_h = 80.0; // floor → underside of flat lid
chamber_inner = 99.0;  // Pyramid 仓内净空 XY（含装配间隙）

/* ===== box (thicker walls) ===== */
wall = 4.5;            // thick chamber wall
floor_t = 2.2;
corner_r = 5.0;
rim = 1.5;             // legacy (chamber size uses chamber_inner)
bay_gap = 0;           // no gap — shared wall with battery bay (saves material)
// Shared low cable passage through the shared wall
cable_pass_h = 18.0;
// Opening on Pyramid wall OPPOSITE the battery bay (outer -X) for mic
bank_wall_open_h = 28.0;   // modest mic window (was 48)
bank_wall_open_y = 0.55;   // fraction of zone_d

/* ===== underside feet (Pyramid side only; battery tower is the other support) ===== */
foot_h = 6.0;          // clearance under floor for sound
foot_strip_w = 6.0;    // thin arc-strip width (saves material vs pad feet)
foot_inset = 1.5;      // pull in from outer outline

/* ===== step seat + flat lid (no magnets) ===== */
lid_t = 2.6;
step = 2.4;            // horizontal ledge the lid sits on
rim_lip = wall - step; // outer lip above the step (keeps lid from sliding out)
lid_clear = 0.5;       // lid slightly smaller than seat opening
pry_w = 24.0;          // front pry opening width
pry_cut = 3.5;         // how deep pry bite cuts into lid front edge

show_ghosts = false;
show_notch_marker = true;

/* ===== derived ===== */
eps = 0.2;
$fn = 48;

bay_xi = pb_t + 2 * pb_clear;
bay_yi = pb_w + 2 * pb_clear;
bay_zi = pb_l + 2 * pb_clear;  // clearance top and bottom

cradle_i = pyramid_xy + 2 * pyramid_clear;
zone_w = chamber_inner;
zone_d = chamber_inner;

plat_outer_w = zone_w + 2 * wall;
plat_outer_d = zone_d + 2 * wall;

// Shared wall: chamber + battery cavity + one outer wall (no bay_gap, no double wall)
// [chamber left wall|zone|SHARED wall|bay|tower outer wall]
outer_w = zone_w + wall + bay_xi + wall + wall; // = plat_outer_w + bay_xi + wall
outer_d = plat_outer_d;

chamber_h = floor_t + post_h + stack_h;
box_h = chamber_h + lid_t;
tower_h = floor_t + bay_zi + 1.5;

pyr_x = -outer_w / 2 + plat_outer_w / 2;
pyr_y = 0;
// Battery cavity center: immediately outside the shared wall
bay_x = -outer_w / 2 + plat_outer_w + bay_xi / 2;
bay_y = 0;
bay_z = floor_t + bay_zi / 2;

// Seat opening (where lid drops in) = inner + 2*step
seat_w = zone_w + 2 * step;
seat_d = zone_d + 2 * step;
// Lid slightly smaller than seat
lid_w = seat_w - 2 * lid_clear;
lid_d = seat_d - 2 * lid_clear;

module rounded_box(x, y, z, r) {
    hull() for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * (x / 2 - r), sy * (y / 2 - r), 0])
            cylinder(h = z, r = r);
}

module feet() {
    // Single thin stadium strip under Pyramid chamber -X edge:
    // straight bar + rounded ends (圆弧条状), less material than two pad feet.
    overlap = 0.8;
    x = pyr_x - plat_outer_w / 2 + foot_strip_w / 2 + foot_inset;
    y_span = plat_outer_d / 2 - foot_strip_w / 2 - foot_inset;
    hull() {
        for (sy = [-1, 1])
            translate([x, sy * y_span, 0])
                cylinder(h = foot_h + overlap, r = foot_strip_w / 2);
    }
}

module posts() {
    // Intentionally empty — no floor bumps in Pyramid chamber
}

module acoustic_vents() {
    // Floor: one opening for speaker — smaller hole, wider frame
    floor_frame = 18.0;
    translate([pyr_x, pyr_y, floor_t / 2])
        cube([
            max(10, zone_w - 2 * floor_frame),
            max(10, zone_d - 2 * floor_frame),
            floor_t + 2
        ], center = true);

    // Side wall vents (front/back) for extra airflow
    for (sy = [-1, 1])
        translate([pyr_x, sy * (plat_outer_d / 2 - wall / 2), floor_t + 12])
            cube([cradle_i * 0.45, wall + 2, 12], center = true);
}

module pyramid_chamber() {
    // Thick walls + step: lid rests on step, held by outer rim_lip
    difference() {
        translate([pyr_x, pyr_y, 0])
            rounded_box(plat_outer_w, plat_outer_d, box_h, corner_r);

        // Inner well up to seat height
        translate([pyr_x, pyr_y, floor_t + chamber_h / 2 + eps / 2])
            cube([zone_w, zone_d, chamber_h + eps], center = true);

        // Seat recess (step): opening through top, leaves rim_lip around outside
        translate([pyr_x, pyr_y, chamber_h + lid_t / 2 + eps / 2])
            cube([seat_w, seat_d, lid_t + eps], center = true);

        // Cable / airflow toward bank (+X) — modest pass only
        translate([pyr_x + zone_w / 2 + wall / 2, pyr_y, floor_t + cable_pass_h / 2])
            cube([wall + 4, zone_d * 0.85, cable_pass_h], center = true);
        // Opposite wall (-X, away from bank): larger opening for mic
        translate([
            pyr_x - zone_w / 2 - wall / 2,
            pyr_y,
            floor_t + bank_wall_open_h / 2
        ])
            cube([
                wall + 4,
                zone_d * bank_wall_open_y,
                bank_wall_open_h
            ], center = true);
        // Extra low USB approach under Pyramid
        translate([pyr_x, pyr_y + cradle_i / 2 - 12, floor_t + 3.5])
            cube([14, 18, 9], center = true);

        acoustic_vents();

        // Front pry gap: cut through outer rim lip so nail can get under lid
        translate([
            pyr_x,
            plat_outer_d / 2 - rim_lip / 2,
            chamber_h + lid_t / 2
        ])
            cube([pry_w, rim_lip + 2, lid_t + 2], center = true);
        // Slight scoop below seat for fingernail
        translate([pyr_x, plat_outer_d / 2 - wall / 2, chamber_h - 2])
            cube([pry_w + 2, wall + 2, 5], center = true);
    }
}

module bank_tower() {
    // Height flush with Pyramid chamber roof; power bank may stick out the top.
    tw = bay_xi + 2 * wall;
    td = bay_yi + 2 * wall;
    total_h = foot_h + box_h;   // same top as Pyramid chamber
    side_win_y = bay_yi * 0.80;
    side_win_bot = foot_h + floor_t;
    // Window up to near the flush top (leave a small rim)
    side_win_top = total_h - 3;
    side_win_h = max(10, side_win_top - side_win_bot);
    bay_cavity_h = total_h - foot_h - floor_t + eps; // open through top
    difference() {
        translate([bay_x, bay_y, 0])
            rounded_box(tw, td, total_h, max(2, corner_r - 2));

        // Battery cavity from pedestal top through the open roof
        translate([
            bay_x,
            bay_y,
            foot_h + floor_t + bay_cavity_h / 2
        ])
            cube([bay_xi + eps, bay_yi + eps, bay_cavity_h], center = true);

        translate([
            outer_w / 2 - wall / 2,
            bay_y,
            side_win_bot + side_win_h / 2
        ])
            cube([wall + 4, side_win_y, side_win_h], center = true);

        // Fully open top (power bank may protrude)
        translate([bay_x, bay_y, total_h - 1])
            cube([bay_xi * 0.98, bay_yi * 0.98, 4], center = true);

        // Cable pass through shared wall
        translate([
            bay_x - bay_xi / 2 - wall / 2,
            bay_y,
            foot_h + floor_t + cable_pass_h / 2
        ])
            cube([wall + 6, min(bay_yi, zone_d) * 0.85, cable_pass_h], center = true);
    }
}

module bridge_floor() {
    // No gap to bridge when walls are shared
}

module base_part() {
    union() {
        feet();
        bank_tower();
        translate([0, 0, foot_h])
            pyramid_chamber();
    }
}

module lid_part() {
    // Flat plate, slightly smaller than seat; front pry bite
    difference() {
        rounded_box(lid_w, lid_d, lid_t, max(1.5, corner_r - 2));

        // Front edge bite — aligns with base pry gap
        translate([0, lid_d / 2 - pry_cut / 2 + 0.2, lid_t / 2])
            cube([pry_w - 2, pry_cut, lid_t + 1], center = true);
        translate([0, lid_d / 2 + 0.5, lid_t * 0.45])
            rotate([90, 0, 0])
                cylinder(h = pry_cut + 2, r = (pry_w - 2) * 0.22, center = true);
    }
}

module assembly() {
    base_part();
    translate([pyr_x, pyr_y, foot_h + chamber_h + 0.1])
        color([0.85, 0.88, 0.92, 0.8])
            lid_part();

    if (show_notch_marker)
        color([1, 0.15, 0.1, 0.9])
            translate([pyr_x, pyr_y + lid_d / 2 + 2, foot_h + chamber_h + lid_t / 2])
                cube([pry_w, 3, lid_t], center = true);
}

module ghosts() {
    color([0.2, 0.55, 0.95, 0.45])
        translate([bay_x, bay_y, foot_h + bay_z])
            cube([pb_t, pb_w, pb_l], center = true);
    color([0.95, 0.45, 0.15, 0.35])
        translate([pyr_x, pyr_y, foot_h + floor_t + post_h + stack_h / 2])
            cube([pyramid_xy, pyramid_xy, stack_h], center = true);
}

if (part == "base") {
    base_part();
} else if (part == "lid") {
    lid_part();
} else {
    assembly();
    if (show_ghosts) ghosts();
}

echo(str("Wall=", wall, " step=", step, " rim_lip=", rim_lip));
echo(str("Chamber inner ", zone_w, "x", zone_d, " (Pyramid ", pyramid_xy, " + gap ", (zone_w - pyramid_xy) / 2, "/side)"));
echo(str("Shared wall (bay_gap=", bay_gap, ") — outer_w=", outer_w));
echo(str("Support: arc-strip foot on Pyramid -X + battery tower to z=0"));
echo(str("Foot strip h=", foot_h, " w=", foot_strip_w));
echo(str("Chamber outer ", plat_outer_w, "x", plat_outer_d, "x", box_h));
echo(str("Seat ", seat_w, "x", seat_d, "  Lid ", lid_w, "x", lid_d, "x", lid_t));
echo(str("Pry gap w=", pry_w, " (no magnets)"));
echo("Export: part=\"base\" and part=\"lid\"");
