    property var personalHomeStartupIntentFile: TextFile { name: "file:///tmp/lg-native-production.__NONCE__/foreground-intent.json" }
    property var personalHomeStartupUptimeFile: TextFile { name: "file:///proc/uptime" }
    property bool personalHomeStartupReleased: false
    property var personalHomeStartupSurface: null

    function personalHomeStartupClock() {
        try {
            var now = parseFloat(personalHomeStartupUptimeFile.read());
            return isFinite(now) && now >= 0 ? now : -1;
        } catch (error) { return -1; }
    }
    function personalHomeStartupPending() {
        if (personalHomeStartupReleased) return false;
        try {
            var intent = JSON.parse(personalHomeStartupIntentFile.read());
            var now = personalHomeStartupClock();
            return intent.nonce === "__NONCE__" && intent.bridge === true && intent.pending === true
                && typeof intent.until === "number" && isFinite(intent.until) && isFinite(now)
                && now >= 0 && intent.until > now && intent.until - now <= 47;
        } catch (error) { return false; }
    }
    function personalHomeStartupEmptyHold(foreground) {
        return Array.isArray(foreground) && foreground.length === 0 && personalHomeStartupPending();
    }
    function personalHomeStartupBridgeMapped(surface) {
        if (!surface || surface.appId !== "com.personalhome.startup" || compositor.fullscreen !== surface
                || !personalHomeStartupPending()) return false;
        personalHomeStartupSurface = surface;
        return true;
    }
    function personalHomeStartupComposed(shown, focused) {
        if (shown === true && focused === true && personalHomeStartupSurface
                && personalHomeStartupSurface === compositor.fullscreen
                && personalHomeStartupSurface.appId === "com.personalhome.startup" && personalHomeStartupPending())
            personalHomeStartupReleased = true;
    }
