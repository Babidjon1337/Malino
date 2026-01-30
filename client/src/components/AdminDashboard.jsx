import React, { useState, useEffect, useRef } from "react";
import {
  Users,
  CreditCard,
  ShoppingCart,
  TrendingUp,
  TrendingDown,
  Minus,
  X,
  Moon,
  Map,
  BookOpen,
  ChevronRight,
  Activity,
  CheckCircle,
  XCircle,
  AlertCircle,
  Crown,
  RefreshCw,
} from "lucide-react";

/**
 * Генерирует массив дат за последние 7 дней в формате DD.MM
 */
const getLast7Days = () => {
  const dates = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    dates.push(`${day}.${month}`);
  }
  return dates;
};

const UI_CONFIG = {
  users: {
    title: "Пользователи",
    color: "blue",
    icon: Users,
  },
  active_subs: {
    title: "Активные подписки",
    color: "orange",
    icon: Crown,
  },
  checkout_initiated: {
    title: "Перешли к оплате",
    color: "yellow",
    icon: CreditCard,
  },
  purchased: {
    title: "Купили",
    color: "green",
    icon: ShoppingCart,
  },
  requests: {
    title: "Всего запросов",
    color: "purple",
  },
};

const BREAKDOWN_CONFIG = {
  1: { title: "Сонник", color: "purple", iconName: "moon" },
  2: { title: "Карта дня", color: "blue", iconName: "map" },
  3: { title: "Таро", color: "pink", iconName: "book" },
};

const calculateTrend = (history) => {
  if (!history || history.length < 2) return "+0";
  const today = history[history.length - 1];
  const yesterday = history[history.length - 2];
  const diff = today - yesterday;

  if (diff > 0) return `+${diff}`;
  if (diff === 0) return "0";
  return `${diff}`;
};

const parseDateTimeString = (str) => {
  if (!str) return new Date();
  const [datePart, timePart] = str.split(" ");
  const [day, month, year] = datePart.split(".").map(Number);
  const [hour, minute] = timePart.split(":").map(Number);
  return new Date(year, month - 1, day, hour, minute);
};

const TrendBadge = ({ value }) => {
  const isPositive = value.startsWith("+");
  const isNegative = value.startsWith("-");

  let colorClass = "text-zinc-400 bg-zinc-500/10 border-zinc-500/10";
  let Icon = Minus;

  if (isPositive) {
    colorClass = "text-emerald-400 bg-emerald-500/10 border-emerald-500/10";
    Icon = TrendingUp;
  } else if (isNegative) {
    colorClass = "text-rose-400 bg-rose-500/10 border-rose-500/10";
    Icon = TrendingDown;
  }

  return (
    <span
      className={`flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-md border ${colorClass}`}
    >
      <Icon size={12} />
      {value}
    </span>
  );
};

const BarChart = ({ data, color, labels }) => {
  const height = 220;
  const width = 320;
  const paddingX = 15;
  const marginTop = 30;
  const marginBottom = 20;
  const graphHeight = height - marginTop - marginBottom;
  const gap = 12;

  // --- Нормализация данных ---
  const count = labels.length;
  const displayData =
    data.length < count
      ? [...Array(count - data.length).fill(0), ...data]
      : data.slice(-count);

  const maxVal = Math.max(...displayData);
  const max = maxVal > 0 ? maxVal * 1.15 : 10;

  const barWidth = (width - paddingX * 2 - gap * (count - 1)) / count;

  const colors = {
    blue: { from: "#3b82f6", to: "#1d4ed8", bg: "rgba(59, 130, 246, 0.2)" },
    green: { from: "#4ade80", to: "#15803d", bg: "rgba(74, 222, 128, 0.2)" },
    yellow: { from: "#facc15", to: "#a16207", bg: "rgba(250, 204, 21, 0.2)" },
    purple: { from: "#c084fc", to: "#7e22ce", bg: "rgba(192, 132, 252, 0.2)" },
    pink: { from: "#f472b6", to: "#be185d", bg: "rgba(244, 114, 182, 0.2)" },
    orange: { from: "#fb923c", to: "#c2410c", bg: "rgba(251, 146, 60, 0.2)" },
  };

  const theme = colors[color] || colors.blue;

  return (
    <div className="w-full flex flex-col items-center mt-2 select-none">
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
      >
        <defs>
          <linearGradient
            id={`grad-${color}`}
            x1="0%"
            y1="0%"
            x2="0%"
            y2="100%"
          >
            <stop offset="0%" stopColor={theme.from} />
            <stop offset="100%" stopColor={theme.to} />
          </linearGradient>
        </defs>

        {displayData.map((val, index) => {
          const barH = (val / max) * graphHeight;
          const x = paddingX + index * (barWidth + gap);
          const y = marginTop + graphHeight - barH;
          const dateLabel = labels[index];

          return (
            <g key={index} className="group">
              <rect
                x={x}
                y={marginTop}
                width={barWidth}
                height={graphHeight}
                fill={theme.bg}
                rx="6"
                ry="6"
                className="opacity-0 group-hover:opacity-30 transition-opacity duration-300"
              />

              {val > 0 && (
                <rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={barH}
                  fill={`url(#grad-${color})`}
                  rx="6"
                  ry="6"
                  className="transition-all duration-300 hover:brightness-110 shadow-[0_0_15px_rgba(0,0,0,0.5)]"
                  style={{ filter: `drop-shadow(0 0 4px ${theme.from})` }}
                />
              )}

              {val === 0 && (
                <rect
                  x={x}
                  y={marginTop + graphHeight - 2}
                  width={barWidth}
                  height={2}
                  fill={theme.bg}
                  rx="1"
                  className="opacity-50"
                />
              )}

              {val > 0 && (
                <text
                  x={x + barWidth / 2}
                  y={y - 8}
                  fill="white"
                  fontSize="13"
                  fontWeight="bold"
                  textAnchor="middle"
                  className="drop-shadow-md opacity-90"
                >
                  {val}
                </text>
              )}

              <text
                x={x + barWidth / 2}
                y={height - 2}
                fill="#71717a"
                fontSize="10"
                fontWeight="500"
                textAnchor="middle"
                className="group-hover:fill-white transition-colors duration-300"
              >
                {dateLabel}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const App = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [userPhoto, setUserPhoto] = useState(null);

  const subscriptionsRef = useRef(null);
  const last7DaysLabels = getLast7Days();

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch("https://malinaezo.ru/api/statistics", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true",
        },
      });

      if (!response.ok) {
        throw new Error(`Ошибка сервера: ${response.status}`);
      }

      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error("Fetch error:", err);
      // Устанавливаем ошибку вместо использования Fallback данных
      setError("Не удалось подключиться к серверу. Попробуйте позже.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.expand();
      tg.setHeaderColor("#09090b");

      if (tg.isVerticalSwipesEnabled !== undefined) {
        tg.isVerticalSwipesEnabled = false;
      }

      document.body.style.backgroundColor = "#09090b";
      document.body.style.overflow = "hidden";
      document.body.style.overscrollBehavior = "none";

      const user = tg.initDataUnsafe?.user;
      if (user?.photo_url) {
        setUserPhoto(user.photo_url);
      }
    }

    return () => {
      document.body.style.overflow = "";
      document.body.style.backgroundColor = "";
      document.body.style.overscrollBehavior = "";
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center text-zinc-400 relative overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-purple-600/20 rounded-full blur-3xl animate-pulse"></div>
        <Activity
          className="animate-spin mb-4 text-blue-500 relative z-10"
          size={32}
        />
        <p className="relative z-10">Синхронизация...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center text-zinc-400 p-4 text-center">
        <div className="p-4 bg-rose-500/10 rounded-full mb-4 text-rose-500">
          <AlertCircle size={32} />
        </div>
        <h2 className="text-white text-xl font-bold mb-2">Ошибка</h2>
        <p className="mb-6 max-w-xs text-sm">{error}</p>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-6 py-3 bg-white text-black font-bold rounded-xl active:scale-95 transition-transform"
        >
          <RefreshCw size={18} /> Обновить
        </button>
      </div>
    );
  }

  if (!stats) return null;

  const conversionRate =
    stats.users.total > 0
      ? ((stats.active_subs.total / stats.users.total) * 100).toFixed(2)
      : "0.00";

  const usersTrend = calculateTrend(stats.users.history);
  const checkoutTrend = calculateTrend(stats.checkout_initiated.history);
  const purchasedTrend = calculateTrend(stats.purchased.history);

  const renderSubscriptionStatus = (sub) => {
    if (sub.recurrent) {
      return (
        <div className="flex items-center justify-center gap-1 text-emerald-400 bg-emerald-500/10 w-full px-1.2 py-0.5 rounded-md border border-emerald-500/10">
          <CheckCircle size={10} />{" "}
          <span className="text-[10px] font-bold">ON</span>
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center gap-1 text-zinc-500 bg-zinc-500/10 w-full px-1.5 py-0.5 rounded-md border border-zinc-500/10">
        <XCircle size={10} /> <span className="text-[9px] font-bold">OFF</span>
      </div>
    );
  };

  const scrollToSubscriptions = () => {
    subscriptionsRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const openMetric = (key, dataObj) => {
    const config = UI_CONFIG[key] || {};
    setSelectedMetric({
      ...dataObj,
      title: config.title || "Статистика",
      color: config.color || "blue",
      labels: last7DaysLabels,
    });
  };

  return (
    <div className="h-screen w-full bg-zinc-950 text-white p-4 font-sans selection:bg-purple-500/30 relative overflow-y-auto overflow-x-hidden pb-12 overscroll-y-contain">
      <div className="fixed -top-20 -left-20 w-80 h-80 bg-purple-600/15 rounded-full blur-[100px] pointer-events-none z-0"></div>
      <div className="fixed top-1/2 -right-20 w-80 h-80 bg-blue-600/15 rounded-full blur-[100px] pointer-events-none z-0"></div>

      <div className="relative z-10 max-w-lg mx-auto pb-8">
        <header className="flex justify-between items-center mb-6 mt-2">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-zinc-400 bg-clip-text text-transparent">
              Admin панель
            </h1>
            <p className="text-xs text-zinc-500">
              Сегодня, {last7DaysLabels[6]}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-zinc-800 border border-white/10 flex items-center justify-center overflow-hidden">
              {userPhoto ? (
                <img
                  src={userPhoto}
                  alt="User"
                  className="w-full h-full object-cover"
                />
              ) : (
                <Users size={16} className="text-zinc-400" />
              )}
            </div>
          </div>
        </header>

        <div className="grid grid-cols-2 gap-3 mb-6">
          <div
            onClick={() => openMetric("users", stats.users)}
            className="bg-zinc-900/60 backdrop-blur-xl border border-white/5 rounded-3xl p-5 active:scale-[0.98] transition-transform cursor-pointer shadow-lg hover:border-blue-500/20 group"
          >
            <div className="flex justify-between items-start mb-2">
              <div className="p-2.5 bg-blue-500/10 rounded-2xl text-blue-400 group-hover:bg-blue-500/20 transition-colors">
                <Users size={22} />
              </div>
            </div>
            <div className="text-3xl font-bold mt-1">{stats.users.total}</div>
            <div className="flex items-center justify-between mt-2">
              <div className="text-zinc-500 text-xs font-medium">
                {UI_CONFIG.users.title}
              </div>
              <TrendBadge value={usersTrend} />
            </div>
          </div>

          <div
            onClick={scrollToSubscriptions}
            className="bg-zinc-900/60 backdrop-blur-xl border border-white/5 rounded-3xl p-5 active:scale-[0.98] transition-transform cursor-pointer shadow-lg hover:border-orange-500/20 group"
          >
            <div className="flex justify-between items-start mb-2">
              <div className="p-2.5 bg-orange-500/10 rounded-2xl text-orange-400 group-hover:bg-orange-500/20 transition-colors">
                <Crown size={22} />
              </div>
            </div>
            <div className="text-3xl font-bold mt-1">
              {stats.active_subs.total}
            </div>
            <div className="text-zinc-500 text-xs font-medium mt-2">
              {UI_CONFIG.active_subs.title}
            </div>
          </div>

          <div
            onClick={() =>
              openMetric("checkout_initiated", stats.checkout_initiated)
            }
            className="bg-zinc-900/60 backdrop-blur-xl border border-white/5 rounded-3xl p-5 active:scale-[0.98] transition-transform cursor-pointer shadow-lg hover:border-yellow-500/20 group"
          >
            <div className="flex justify-between items-start mb-3">
              <div className="w-10 h-10 flex items-center justify-center bg-yellow-500/10 rounded-2xl text-yellow-400 group-hover:bg-yellow-500/20 transition-colors">
                <CreditCard size={20} />
              </div>
              <TrendBadge value={checkoutTrend} />
            </div>
            <div className="text-2xl font-bold">
              {stats.checkout_initiated.total}
            </div>
            <div className="text-zinc-500 text-xs font-medium mt-1">
              {UI_CONFIG.checkout_initiated.title}
            </div>
          </div>

          <div
            onClick={() => openMetric("purchased", stats.purchased)}
            className="bg-zinc-900/60 backdrop-blur-xl border border-white/5 rounded-3xl p-5 active:scale-[0.98] transition-transform cursor-pointer shadow-lg hover:border-emerald-500/20 group relative overflow-hidden"
          >
            <div className="absolute -right-6 -top-6 w-20 h-20 bg-emerald-500/20 blur-2xl rounded-full"></div>
            <div className="flex justify-between items-start mb-3 relative z-10">
              <div className="w-10 h-10 flex items-center justify-center bg-emerald-500/10 rounded-2xl text-emerald-400 group-hover:bg-emerald-500/20 transition-colors">
                <ShoppingCart size={20} />
              </div>
              <TrendBadge value={purchasedTrend} />
            </div>
            <div className="text-2xl font-bold relative z-10">
              {stats.purchased.total}
            </div>
            <div className="text-zinc-500 text-xs font-medium mt-1 relative z-10">
              {UI_CONFIG.purchased.title}
            </div>
          </div>

          <div className="col-span-2 bg-white/5 border border-white/5 rounded-2xl p-3 flex items-center justify-between backdrop-blur-md">
            <div className="flex items-center gap-2 text-zinc-400 text-sm">
              <Activity size={16} />
              <span>Конверсия</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">
                от всех пользователей
              </span>
              <span className="font-bold text-white text-sm bg-white/10 px-2 py-1 rounded-lg border border-white/5">
                {conversionRate}%
              </span>
            </div>
          </div>
        </div>

        <div className="mb-8">
          <div className="flex justify-between items-start mb-4 px-1">
            <div>
              <h2 className="text-zinc-400 text-xs font-medium uppercase tracking-wider">
                {UI_CONFIG.requests.title}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-3xl font-bold text-white">
                  {stats.requests.total}
                </span>
                <TrendBadge value={calculateTrend(stats.requests.history)} />
              </div>
              <div className="text-zinc-500 text-[10px] font-medium mt-1">
                запросов за сегодня
              </div>
            </div>
            <button
              onClick={() => openMetric("requests", stats.requests)}
              className="text-xs text-blue-400 font-medium flex items-center gap-1 hover:text-blue-300 transition-colors bg-blue-500/10 px-3 py-1.5 rounded-full"
            >
              График <ChevronRight size={12} />
            </button>
          </div>

          <div className="flex flex-col gap-2">
            {stats.requests.breakdown.map((item) => {
              const config = BREAKDOWN_CONFIG[item.id] || {
                title: "Unknown",
                color: "gray",
                iconName: "activity",
              };
              const itemTrend = calculateTrend(item.history);
              const isItemNegative = itemTrend.startsWith("-");
              const percent =
                stats.requests.total > 0
                  ? Math.round((item.total / stats.requests.total) * 100)
                  : 0;

              return (
                <div
                  key={item.id}
                  onClick={() =>
                    setSelectedMetric({
                      ...item,
                      title: config.title,
                      color: config.color,
                      labels: last7DaysLabels,
                    })
                  }
                  className="bg-zinc-900/40 backdrop-blur-md border border-white/5 rounded-2xl p-4 flex items-center gap-4 active:scale-[0.98] transition-all hover:bg-zinc-800/50 cursor-pointer"
                >
                  <div
                    className={`w-12 h-12 rounded-2xl flex items-center justify-center bg-gradient-to-br ${
                      config.color === "purple"
                        ? "from-purple-500/20 to-purple-600/5 text-purple-400"
                        : config.color === "blue"
                          ? "from-blue-500/20 to-blue-600/5 text-blue-400"
                          : "from-pink-500/20 to-pink-600/5 text-pink-400"
                    }`}
                  >
                    {config.iconName === "moon" && <Moon size={20} />}
                    {config.iconName === "map" && <Map size={20} />}
                    {config.iconName === "book" && <BookOpen size={20} />}
                  </div>

                  <div className="flex-1">
                    <div className="flex justify-between mb-2">
                      <span className="text-base font-semibold text-zinc-100">
                        {config.title}
                      </span>
                      <div className="text-right">
                        <span className="block text-sm font-bold text-white">
                          {item.total}
                        </span>
                      </div>
                    </div>
                    <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          config.color === "purple"
                            ? "bg-purple-500"
                            : config.color === "blue"
                              ? "bg-blue-500"
                              : "bg-pink-500"
                        }`}
                        style={{
                          width: `${percent}%`,
                          boxShadow: `0 0 10px ${config.color}`,
                        }}
                      ></div>
                    </div>
                    <div className="flex justify-between mt-1.5">
                      <span className="text-[10px] text-zinc-500">
                        Нагрузка
                      </span>
                      <span
                        className={`text-[10px] font-medium ${isItemNegative ? "text-rose-400" : "text-emerald-400"}`}
                      >
                        {itemTrend}
                      </span>
                    </div>
                  </div>

                  <ChevronRight size={16} className="text-zinc-600" />
                </div>
              );
            })}
          </div>
        </div>

        <div className="mb-6" ref={subscriptionsRef}>
          <h2 className="text-xl font-bold text-white mb-4 px-1">
            Активные подписки
          </h2>
          <div className="bg-zinc-900/40 backdrop-blur-md border border-white/5 rounded-3xl overflow-hidden shadow-lg">
            <div className="w-full px-2 py-2">
              <table className="w-full text-left border-collapse table-fixed">
                <thead>
                  <tr className="border-b border-white/5 text-zinc-500 text-[10px] uppercase tracking-wider">
                    <th className="py-2 px-1 font-medium text-center w-[7%]">
                      #
                    </th>
                    <th className="py-2 px-1 font-medium text-center w-[16%]">
                      Rec.
                    </th>
                    <th className="py-2 px-1 font-medium text-center w-[25%]">
                      Цена
                    </th>
                    <th className="py-2 px-2 font-medium w-[25%]">Начало</th>
                    <th className="py-2 px-3 font-medium w-[25%]">Конец</th>
                    <th className="py-2 px-1 font-medium text-center w-[12%]">
                      Поп.
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {[...stats.subscriptions]
                    .sort((a, b) => {
                      return (
                        parseDateTimeString(a.end) - parseDateTimeString(b.end)
                      );
                    })
                    .map((sub, index) => (
                      <tr
                        key={index}
                        className="hover:bg-white/5 transition-colors text-[12px]"
                      >
                        <td className="py-2 px-1 text-zinc-400 font-mono text-center">
                          {index + 1}
                        </td>
                        <td className="py-2 px-1">
                          {renderSubscriptionStatus(sub)}
                        </td>
                        <td className="py-2 px-1 text-[14px] font-bold text-white text-center">
                          {sub.price}
                        </td>
                        <td className="py-2 px-1 whitespace-nowrap text-[12px]">
                          <div className="flex flex-col">
                            <span className="text-zinc-300">
                              {sub.start.split(" ")[0]}
                            </span>
                            <span className="text-[11px] text-zinc-500  leading-tight">
                              {sub.start.split(" ")[1]}
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-1 whitespace-nowrap text-[12px]">
                          <div className="flex flex-col">
                            <span className="text-white font-medium">
                              {sub.end.split(" ")[0]}
                            </span>
                            <span className="text-[11px] text-zinc-500 leading-tight">
                              {sub.end.split(" ")[1]}
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-1 text-center">
                          <div className="flex items-center justify-center text-[12px] gap-1">
                            {sub.attempts === 0 ? (
                              <span className="text-zinc-500 font-medium">
                                0
                              </span>
                            ) : (
                              <div className="flex items-center gap-0.5 text-orange-400 font-bold">
                                <AlertCircle size={10} /> {sub.attempts}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {selectedMetric && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-0 sm:px-4 pb-0 sm:pb-4">
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm transition-opacity"
            onClick={() => setSelectedMetric(null)}
          ></div>

          <div className="relative w-full max-w-md bg-[#121214] border-t border-white/10 sm:border rounded-t-[32px] sm:rounded-3xl p-6 shadow-2xl animate-slide-up ring-1 ring-white/10 pb-10">
            <div className="w-12 h-1.5 bg-zinc-800 rounded-full mx-auto mb-6"></div>

            <div className="flex justify-between items-start mb-2">
              <div>
                <h3 className="text-zinc-400 text-sm font-medium tracking-wide">
                  {selectedMetric.title}
                </h3>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-4xl font-bold text-white tracking-tight">
                    {selectedMetric.total}
                  </span>
                  {selectedMetric.history && (
                    <TrendBadge
                      value={calculateTrend(selectedMetric.history)}
                    />
                  )}
                </div>
              </div>
              <button
                onClick={() => setSelectedMetric(null)}
                className="p-2 bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {selectedMetric.history && (
              <div className="mb-6">
                <BarChart
                  data={selectedMetric.history}
                  color={selectedMetric.color}
                  labels={selectedMetric.labels || last7DaysLabels}
                />
              </div>
            )}

            <button
              onClick={() => setSelectedMetric(null)}
              className="w-full py-4 bg-white text-black font-bold text-lg rounded-2xl active:scale-95 transition-transform hover:bg-zinc-200"
            >
              Отлично
            </button>
          </div>
        </div>
      )}

      <style>{`
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #09090b; }
        ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }

        @keyframes slide-up {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
        .animate-slide-up {
          animation: slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
    </div>
  );
};

export default App;
