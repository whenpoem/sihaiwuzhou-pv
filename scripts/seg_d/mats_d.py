"""D 段的显卡材质。导入本模块即完成注册。

颜色在与引擎相同的空间里计算（数值即显示用的 sRGB 值，允许超过 1 表示高光），所有平面都在 past 组，
由过去的调色加上光晕、颗粒和暖色。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import register_material  # noqa: E402

# 雨点打在水面上的涟漪：把地面分成边长 cell 的格子，每格每个周期落一滴，落点和时刻由格子号决定；
# 返回高度场的梯度（xy）和刚落下时溅起的亮点（z）。查本格和周围 8 格，涟漪越过格子边界时不会被截断。
RIPPLE = """
// 圆形水洼的边：irr 为 1 时边缘随角度起伏（真实水洼不是正圆），为 0 时是正圆（之后变成地球的轮廓）
float pool_edge(vec2 d, float pr, float irr) {
    float ang = atan(d.y, d.x);
    float n = vnoise(vec2(cos(ang), sin(ang)) * 2.2 + 7.0, 83) - 0.5;
    float n2 = vnoise(vec2(cos(ang), sin(ang)) * 5.5 + 3.0, 84) - 0.5;
    return pr * (1.0 + irr * (0.10 * n + 0.04 * n2));
}

vec3 ripple_layer(vec2 p, float t, float cell, float period, float speed, int seed) {
    vec2 g = floor(p / cell);
    vec3 acc = vec3(0.0);
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            ivec2 c = ivec2(g) + ivec2(i, j);
            float r1 = rnd(c, seed), r2 = rnd(c, seed + 1), r3 = rnd(c, seed + 2);
            float ph = t / period + r3;
            float k = floor(ph);
            float tau = fract(ph) * period;
            vec2 ctr = (vec2(c) + vec2(rnd(c + ivec2(int(k) * 7, 0), seed + 3), rnd(c + ivec2(0, int(k) * 5), seed + 4))) * cell;
            vec2 d = p - ctr;
            float dist = length(d) + 1e-5;
            float rad = tau * speed;
            float x = (dist - rad) / (cell * 0.16);
            float env = exp(-x * x) * exp(-tau / (period * 0.32)) * step(0.0, rad - 0.0);
            float dh = -2.0 * x * env * cos(x * 3.0) - 3.0 * env * sin(x * 3.0);
            acc.xy += dh * d / dist * (0.6 + 0.4 * r1);
            acc.z += exp(-dist * dist / (cell * cell * 0.012)) * exp(-tau / 0.035) * (0.5 + r2);
        }
    }
    return acc;
}
"""

# 雨夜湿透的砖地，俯视。底色是平铺的砖地照片；aux 为同样平铺的辅助图：R 砖缝（积水），G 砖面高度。
# 光：远处路灯（点光源，暖色）+ 夜空的冷色环境光 + 闪电（整片天空发亮）。湿砖变暗、变饱和；砖缝和低洼处是水面，
# 像镜子一样映出路灯和天空，雨点在水面上不断激起涟漪，把映出的路灯打碎成闪动的光斑。
# 干地（单车躺过的地方）：bikemask 按 bike_rect 摆放，干处颜色发浅、没有反光和涟漪，边缘一圈水痕略深；
# 雨点落进干地，留下一个个深色湿斑，湿斑越来越密，最后连成一片，轮廓消失。
register_material("d_wetground", RIPPLE + """
uniform sampler2D aux;
uniform sampler2D bikemask;
uniform vec4 bike_rect;        // 干地在平面局部坐标里的范围 (x0, y0, x1, y1)，y 向上
uniform float bike_rot;        // 干地绕自身中心的转角（弧度）
uniform vec3 lamp_pos;
uniform vec3 lamp_col;
uniform vec3 amb;
uniform vec3 sky;              // 夜空（反射里看到的）
uniform float flash;
uniform float wet_t0;          // 干地开始被打湿的时刻
uniform float wet_t1;          // 干地完全湿透的时刻
uniform float dry_on;          // 干地是否存在（0–1）
uniform float puddle_amt;      // 地面积水的多少
uniform float rain_k;          // 雨的强度（涟漪的多少）
uniform vec2 pool_c;           // 圆形水洼中心（世界坐标），水洼里另由 d_puddle 画，这里留出地面
uniform float pool_r;
uniform float pool_irr;
uniform vec3 moon_dir;
uniform vec4 imp0;             // 重物砸进积水激起的大涟漪：(x, y, 时刻, 强度)
uniform vec4 imp1;
uniform vec4 imp2;


// 月亮的倒影：方向 moon_dir，视直径约 2.2°，带一圈月晕；涟漪把它打碎、晃动
vec3 moon_refl(vec3 R) {
    float c = dot(normalize(R), moon_dir);
    float ang = acos(clamp(c, -1.0, 1.0));
    float disc = smoothstep(0.0215, 0.0185, ang);
    vec2 q = vec2(R.x - moon_dir.x, R.y - moon_dir.y) * 60.0;
    float mare = 0.82 + 0.18 * fbm(q + 3.0, 3, 0.05, 61);
    float halo = exp(-ang * ang / 0.0016) * 0.35 + exp(-ang / 0.05) * 0.10;
    return vec3(1.05, 1.02, 0.94) * (disc * mare * 2.2 + halo);
}

// 大涟漪：一圈圈向外扩散的水波，返回高度梯度（xy）与被推开的水造成的明暗（z）
vec3 impact(vec4 im, vec2 p, float t) {
    float u = t - im.z;
    if (u < 0.0 || im.w <= 0.0) return vec3(0.0);
    vec2 d = p - im.xy;
    float dist = length(d) + 1e-4;
    float front = 0.18 + 1.1 * u;                    // 波前半径（米）
    float x = (dist - front) / 0.05;
    float env = exp(-max(x, 0.0) * max(x, 0.0) * 0.5) * smoothstep(-9.0, -1.0, x) * exp(-u / 0.55) * im.w;
    float ph = (dist - front) * 70.0;
    float dh = cos(ph) * env;
    return vec3(dh * d / dist, sin(ph) * env);
}

vec4 material(vec4 base) {
    vec2 uv = v_uv;
    vec4 ax = texture(aux, uv);
    vec2 texel = 1.0 / vec2(textureSize(aux, 0));
    float hx = texture(aux, uv + vec2(texel.x, 0.0)).g - texture(aux, uv - vec2(texel.x, 0.0)).g;
    float hy = texture(aux, uv + vec2(0.0, texel.y)).g - texture(aux, uv - vec2(0.0, texel.y)).g;
    vec3 P = v_wpos;
    float t = u_time;

    // 大块的低洼积水（不随砖地平铺重复）
    float big = fbm(P.xy * 1.1 + vec2(3.7, 1.3), 4, length(fwidth(P.xy)) * 1.1, 41);
    float pud = clamp(ax.r * 0.85 + smoothstep(0.50, 0.62, big) * puddle_amt, 0.0, 1.0);
    // 圆形水洼外面一圈：水从水洼边漫到砖面上，越靠近水边越湿、越亮
    float pe = pool_edge(P.xy - pool_c, pool_r, pool_irr);
    float pdist = length(P.xy - pool_c) - pe;
    float halo = pool_r > 0.0 ? exp(-max(pdist, 0.0) / 0.05) * smoothstep(-0.01, 0.005, pdist) : 0.0;
    halo *= 0.75 + 0.25 * vnoise(P.xy * 40.0, 85);
    pud = max(pud, halo * 0.85);

    // 干地
    float dry = 0.0;
    if (dry_on > 0.001) {
        vec2 bc = 0.5 * (bike_rect.xy + bike_rect.zw);
        vec2 q = v_local - bc;
        float cr = cos(-bike_rot), sr = sin(-bike_rot);
        q = vec2(cr * q.x - sr * q.y, sr * q.x + cr * q.y) + bc;
        vec2 bu = (q - bike_rect.xy) / (bike_rect.zw - bike_rect.xy);
        if (bu.x > 0.0 && bu.x < 1.0 && bu.y > 0.0 && bu.y < 1.0) {
            vec2 tb = vec2(bu.x, 1.0 - bu.y);
            float m = texture(bikemask, tb).r;
            float soft = textureLod(bikemask, tb, 4.5).r;
            // 雨点打湿干地：边长 1.6 厘米的格子，每格一个湿斑，落下的时刻在 [wet_t0, wet_t1] 里先疏后密
            float wetted = 0.0;
            vec2 g = floor(q / 0.016);
            for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
                ivec2 c = ivec2(g) + ivec2(i, j);
                float th = mix(wet_t0, wet_t1, pow(rnd(c, 71), 1.5));
                vec2 ctr = (vec2(c) + vec2(rnd(c, 72), rnd(c, 73))) * 0.016;
                float rr = 0.007 + 0.006 * rnd(c, 74);
                float grow = smoothstep(th, th + 0.04, t) * (1.0 + 0.5 * smoothstep(th, th + 0.5, t));
                wetted = max(wetted, smoothstep(rr * grow + 0.002, rr * grow - 0.002, length(q - ctr)) * step(th, t));
            }
            float fade = smoothstep(wet_t1 - 0.25, wet_t1 + 0.1, t);
            dry = m * (1.0 - wetted) * (1.0 - fade) * dry_on;
            // 干湿交界处水往干地里渗，一圈略深的水痕
            pud *= 1.0 - m * dry_on * (1.0 - fade) * 0.9;
            pud += clamp(soft - m, 0.0, 1.0) * 0.6 * dry_on * (1.0 - fade);
        }
    }

    // 涟漪（只在水里），两层格子叠加
    vec3 r1 = ripple_layer(P.xy, t, 0.11, 0.85, 0.16, 11);
    vec3 r2 = ripple_layer(P.xy + vec2(0.037, 0.051), t + 0.31, 0.08, 0.7, 0.13, 23);
    vec3 rip = (r1 + r2 * 0.8) * rain_k;
    vec3 ib = impact(imp0, P.xy, t) + impact(imp1, P.xy, t) + impact(imp2, P.xy, t);
    rip.xy += ib.xy * 9.0;
    float wetness = 1.0 - dry;
    float rk = 0.07 * pud + 0.008 * (1.0 - pud);
    vec3 n = normalize(vec3(-hx * 3.0 * (1.0 - pud) - rip.x * rk, -hy * 3.0 * (1.0 - pud) - rip.y * rk, 1.0));
    n = normalize(mix(vec3(0.0, 0.0, 1.0), n, wetness));

    // 漫反射：湿砖变暗变饱和，干砖发浅发灰
    vec3 alb = base.rgb;
    float lum = dot(alb, vec3(0.333));
    vec3 wetalb = pow(alb, vec3(1.2)) * 0.78;
    vec3 dryalb = mix(alb, vec3(lum), 0.45) * 1.75 + 0.06;
    vec3 a = mix(wetalb, dryalb, dry);
    a = mix(a, a * 0.55, pud * wetness);                       // 积水处更暗，主要靠反射
    vec3 Ld = lamp_pos - P;
    float dl = length(Ld);
    Ld /= dl;
    // 路灯带灯罩，光往下照：照度 ∝ cos^3(偏离竖直的角) / 距离²，灯下一圈最亮，往外暗下去
    float cdown = Ld.z;
    float fall = pow(max(cdown, 0.0), 3.0) / (dl * dl) * 9.0;
    vec3 col = a * (amb + lamp_col * fall * max(dot(n, Ld), 0.0) + flash * vec3(0.85, 0.92, 1.05));

    // 反射：路灯与夜空
    vec3 V = normalize(u_eye - P);
    vec3 R = reflect(-V, n);
    float cosr = max(dot(R, Ld), 0.0);
    float mirror = pud * wetness;
    float gloss = (1.0 - pud) * wetness;
    float lampI = 9.0 / (dl * dl);
    float spec = pow(cosr, 260.0) * 7.0 * mirror + pow(cosr, 40.0) * 0.9 * gloss + pow(cosr, 8.0) * 0.10 * gloss;
    float fres = 0.10 + 0.25 * pow(1.0 - max(dot(V, n), 0.0), 3.0);
    // 水面映出的夜云：按反射方向投到一层假想的云上，镜头移动时有视差，涟漪把它扭碎
    vec2 sp = R.xy / max(R.z, 0.25) * 1.6 + vec2(t * 0.03, t * 0.01);
    float cl = fbm(sp * 1.3 + 4.0, 5, length(fwidth(sp)) * 1.3, 5);
    vec3 skyc = sky * (0.45 + 1.4 * smoothstep(0.38, 0.80, cl)) + flash * vec3(2.2, 2.35, 2.7);
    col += lamp_col * lampI * spec;
    col += skyc * (mirror * 0.85 + gloss * fres * 0.5) * (1.0 + ib.z * 0.8);
    col += moon_refl(R) * (mirror * 0.9 + gloss * 0.08);
    // 重物砸下激起的水波：波峰处一圈被路灯照亮的水光
    col += (lamp_col * (fall * 1.5 + 0.10) + vec3(0.06, 0.07, 0.09)) * max(ib.z, 0.0) * 0.55 * wetness;
    // 雨点溅起的亮点：被路灯和闪电照亮
    col += (lamp_col * (fall * 2.0 + 0.04) + flash * vec3(1.2)) * rip.z * 0.9 * wetness;

    // 圆形水洼的位置留给 d_puddle
    float a_out = pool_r > 0.0 ? smoothstep(-0.010, 0.010, pdist) : 1.0;
    return vec4(col * a_out, a_out);
}
""", defaults={"bike_rect": (0.0, 0.0, 1.0, 1.0), "bike_rot": 0.0, "lamp_pos": (-3.0, 2.0, 4.5),
               "lamp_col": (1.0, 0.72, 0.42), "amb": (0.035, 0.042, 0.06), "sky": (0.05, 0.055, 0.07),
               "flash": 0.0, "wet_t0": 77.5, "wet_t1": 78.6, "dry_on": 1.0, "puddle_amt": 1.0, "rain_k": 1.0,
               "pool_c": (100.0, 100.0), "pool_r": 0.0, "pool_irr": 0.0, "moon_dir": (0.0, 0.0, -1.0),
               "imp0": (0.0, 0.0, 1e4, 0.0), "imp1": (0.0, 0.0, 1e4, 0.0), "imp2": (0.0, 0.0, 1e4, 0.0)})

# 圆形积水：映出夜云和路灯的水面，雨点涟漪；drop_t 时一滴大雨落在正中，激起一圈圈同心波纹，freeze_t 起波纹
# 停止扩散、定成等距的圆环（之后变成球的纬线），rings 控制这些圆环亮线的显现。
register_material("d_puddle", RIPPLE + """
uniform vec2 pc;               // 水洼中心（世界坐标）
uniform float pr;              // 水洼半径
uniform float irr;             // 边缘的不规则程度
uniform vec3 lamp_pos;
uniform vec3 lamp_col;
uniform vec3 lamp_rdir;        // 路灯倒影的方向（见 scene.reflect_dir：倒影固定落在水洼里靠路灯的一侧）
uniform vec3 sky;
uniform float flash;
uniform float drop_t;
uniform float freeze_t;
uniform float rings;
uniform float level;           // 水量：1 满，0 干
uniform vec3 moon_dir;

// 月亮的倒影：方向 moon_dir，视直径约 2.2°，带一圈月晕；涟漪把它打碎、晃动
vec3 moon_refl(vec3 R) {
    float c = dot(normalize(R), moon_dir);
    float ang = acos(clamp(c, -1.0, 1.0));
    float disc = smoothstep(0.0215, 0.0185, ang);
    vec2 q = vec2(R.x - moon_dir.x, R.y - moon_dir.y) * 60.0;
    float mare = 0.82 + 0.18 * fbm(q + 3.0, 3, 0.05, 61);
    float halo = exp(-ang * ang / 0.0005) * 0.22 + exp(-ang / 0.02) * 0.04;
    return vec3(0.95, 0.98, 1.05) * (disc * mare * 1.6 + halo);
}

// 路灯的倒影：灯泡是一个亮核，灯罩下沿一圈光晕
vec3 lamp_refl(vec3 R) {
    float c = dot(normalize(R), lamp_rdir);
    float ang = acos(clamp(c, -1.0, 1.0));
    return lamp_col * (smoothstep(0.011, 0.006, ang) * 5.0 + exp(-ang * ang / 0.00035) * 0.9 + exp(-ang / 0.025) * 0.06);
}

vec4 material(vec4 base) {
    vec3 P = v_wpos;
    vec2 d = P.xy - pc;
    float r = length(d) + 1e-5;
    float t = u_time;
    float pe = pool_edge(d, pr, irr);
    float inside = smoothstep(pe + 0.010, pe - 0.010, r);
    if (inside <= 0.0) return vec4(0.0);
    // 雨点涟漪：两层格子，把倒影打碎
    vec3 rp = ripple_layer(P.xy, t, 0.07, 0.75, 0.16, 31) + 0.8 * ripple_layer(P.xy + 0.03, t + 0.4, 0.055, 0.6, 0.13, 37);
    // 同心波纹：波前以 0.55 米/秒扩散，定住以后保持
    float te = max(min(t, freeze_t) - drop_t, 0.0);
    float front = 0.55 * te;
    float lam = pr / 7.0;                                  // 环距
    float x = r - front;
    float env = (t > drop_t) ? smoothstep(0.02, -0.10, x) : 0.0;
    float ph = (r / lam) * 6.2831853 - te * 6.0;
    float amp = env * mix(exp(-te * 0.8), 1.0, smoothstep(freeze_t - 0.2, freeze_t, t));
    float dh = cos(ph) * amp;
    vec2 g = rp.xy * 0.022 + dh * d / r * 0.30;
    vec3 n = normalize(vec3(-g, 1.0));
    vec3 V = normalize(u_eye - P);
    vec3 R = reflect(-V, n);
    // 水面映出的夜云
    vec2 sp = R.xy / max(R.z, 0.25) * 1.6 + vec2(t * 0.03, t * 0.01);
    float cl = fbm(sp * 1.3 + 4.0, 5, length(fwidth(sp)) * 1.3, 5);
    vec3 skyp = sky * (0.22 + 2.2 * smoothstep(0.40, 0.84, cl)) + flash * vec3(2.2, 2.35, 2.7);
    vec3 Ld = normalize(lamp_pos - P);
    float dl = length(lamp_pos - P);
    float fall = pow(max(Ld.z, 0.0), 3.0) * 9.0 / (dl * dl);
    vec3 col = vec3(0.010, 0.012, 0.016) + skyp * 0.85 + lamp_refl(R) + moon_refl(R);
    col += (lamp_col * (fall * 2.0 + 0.05) + flash) * max(rp.z, 0.0) * 0.35;    // 雨点落下溅起的亮点
    // 涟漪的环被天光勾出细细的亮线
    col += sky * 2.5 * clamp(length(rp.xy) * 0.06, 0.0, 1.0);
    // 定住的圆环：波峰处一道细亮线，像纬线
    float crest = pow(max(cos(ph), 0.0), 18.0) * env * rings;
    col += vec3(0.75, 0.70, 0.62) * crest * 2.2;
    // 水边：水变浅，透出一点湿砖的暗褐色，水线处一道被路灯照亮的细亮边
    float edge = smoothstep(pe * 0.80, pe, r);
    col = mix(col, col * 0.6 + vec3(0.035, 0.024, 0.016), edge * 0.6);
    col += lamp_col * fall * 0.45 * exp(-pow((r - pe * 0.985) / 0.004, 2.0));
    float a = inside * level;
    return vec4(col * a, a);
}
""", defaults={"pc": (0.0, 0.0), "pr": 0.4, "irr": 0.0, "lamp_pos": (-3.9, 2.3, 3.6), "lamp_col": (1.0, 0.8, 0.6),
               "lamp_rdir": (0.0, 0.0, -1.0), "sky": (0.17, 0.2, 0.27), "flash": 0.0, "drop_t": 1e4, "freeze_t": 1e4,
               "rings": 0.0, "level": 1.0, "moon_dir": (0.0, 0.0, -1.0)})

# 被一盏灯照亮的不透明物体（桌面、拼图块、立方体）：漫反射加一点印刷面的光泽。底色为贴图（直通 alpha 已预乘），
# 灯在 lamp_pos，环境光 amb；gloss 为光泽强度。
register_material("d_lit", """
uniform vec3 lamp_pos;
uniform vec3 lamp_col;
uniform vec3 amb;
uniform float gloss;
uniform float lamp_fall;
vec4 material(vec4 base) {
    vec3 P = v_wpos;
    vec3 Ld = lamp_pos - P;
    float dl = length(Ld);
    Ld /= dl;
    float fall = 1.0 / (1.0 + dl * dl * lamp_fall);
    vec3 n = vec3(0.0, 0.0, 1.0);
    vec3 col = base.rgb * (amb + lamp_col * fall * max(dot(n, Ld), 0.0));
    vec3 V = normalize(u_eye - P);
    vec3 H = normalize(Ld + V);
    col += lamp_col * fall * pow(max(dot(n, H), 0.0), 30.0) * gloss * base.a;
    return vec4(col, base.a);
}
""", defaults={"lamp_pos": (0.0, 0.0, 3.0), "lamp_col": (1.0, 0.8, 0.6), "amb": (0.05, 0.05, 0.06), "gloss": 0.0,
               "lamp_fall": 0.3})
