<?php

use App\Http\Controllers\ProfileController;
use Illuminate\Foundation\Application;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

// 🟢 Імпорт моделей
use App\Models\Feedback;
use App\Models\ScanHistory;

/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
*/

// Головна сторінка
Route::get('/', function () {
    return Inertia::render('Welcome', [
        'canLogin' => Route::has('login'),
        'canRegister' => Route::has('register'),
        'laravelVersion' => Application::VERSION,
        'phpVersion' => PHP_VERSION,
    ]);
});

// Дашборд (доступний тільки авторизованим) З ІСТОРІЄЮ ТА СТАТИСТИКОЮ
Route::get('/dashboard', function () {
    $user = auth()->user();
    
    // Беремо останні 10 перевірок поточного користувача
    $history = ScanHistory::where('user_id', $user->id)
        ->latest()
        ->take(10)
        ->get();

    // Рахуємо статистику поточного користувача
    $total = ScanHistory::where('user_id', $user->id)->count();
    $spamCount = ScanHistory::where('user_id', $user->id)->where('is_spam', true)->count();

    return Inertia::render('Dashboard', [
        'initialHistory' => $history,
        'initialStats' => [
            'total' => $total,
            'spam' => $spamCount,
            'safe' => $total - $spamCount,
        ]
    ]);
})->middleware(['auth', 'verified'])->name('dashboard');

// Налаштування профілю
Route::middleware('auth')->group(function () {
    Route::get('/profile', [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile', [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');
});

/**
 * 🤖 МАРШРУТ 1: Перевірка тексту через Python AI та ЗБЕРЕЖЕННЯ ІСТОРІЇ
 */
Route::post('/check-spam', function (Request $request) {
    $text = $request->input('text');
    $sender = $request->input('sender');
    $senderDomain = $request->input('senderDomain');

    try {
        // Звертаємося до нашого Python-сервера на порту 9000
        $response = Http::timeout(10)->post('http://127.0.0.1:9000/analyze', [
            'text' => $text,
            'sender' => $sender,
            'sender_domain' => $senderDomain,
        ]);

        if ($response->successful()) {
            $data = $response->json();
            $score = $data['spam_score'];
            $threshold = $data['base_threshold'] ?? 0.55;

            // 💾 ЗБЕРІГАЄМО ЗАПИС У БАЗУ ДАНИХ ДЛЯ ПОТОЧНОГО КОРИСТУВАЧА
            $historyPayload = [
                'user_id' => auth()->id(),
                'score' => $score,
                'is_spam' => $score >= $threshold,
            ];

            // Поки міграція з email_preview не застосована, не валимо аналіз через відсутню колонку.
            if (Schema::hasColumn('scan_histories', 'email_preview')) {
                $historyPayload['email_preview'] = Str::limit(trim(preg_replace('/\s+/u', ' ', $text ?? '')), 220, '...');
            }

            if (Schema::hasColumn('scan_histories', 'email_text')) {
                $historyPayload['email_text'] = $text;
            }

            ScanHistory::create($historyPayload);

            return $data;
        }
        
        return response()->json(['error' => 'Python server error'], 500);

    } catch (\Exception $e) {
        return response()->json(['error' => 'Connection failed: ' . $e->getMessage()], 500);
    }
})->middleware(['auth']);

/**
 * 💾 МАРШРУТ 2: Збереження відгуку та ВІДПРАВКА В PYTHON НА НАВЧАННЯ
 */
Route::post('/save-feedback', function (Request $request) {
    // Валідація даних
    $validated = $request->validate([
        'text'      => 'required|string',
        'score'     => 'required|numeric',
        'isSpam'    => 'required|boolean',
        'isCorrect' => 'required|boolean',
        'sender'    => 'nullable|string',
        'senderDomain' => 'nullable|string',
    ]);

    // 1. Створення запису в таблиці feedback на сайті
    Feedback::create([
        'user_id'            => auth()->id(),
        'email_text'         => $validated['text'],
        'ai_score'           => $validated['score'],
        'is_spam_prediction' => $validated['isSpam'],
        'is_user_agrees'     => $validated['isCorrect'],
    ]);

    // 2. 🧠 ВІДПРАВЛЯЄМО В PYTHON (на порт 9000), ЩОБ МОДЕЛЬ ПЕРЕНАВЧИЛАСЯ
    $pythonLearnMeta = [
        'retrain_scheduled' => false,
        'retrain_in_progress' => false,
        'retrain_started_at' => null,
        'retrain_last_finished_at' => null,
        'retrain_last_status' => null,
        'retrain_last_error' => null,
    ];

    try {
        $pythonResponse = Http::timeout(5)->post('http://127.0.0.1:9000/learn', [
            'text' => $validated['text'],
            'is_spam_predicted' => $validated['isSpam'],
            'is_correct' => $validated['isCorrect'],
            'sender' => $validated['sender'] ?? null,
            'sender_domain' => $validated['senderDomain'] ?? null,
        ]);

        if ($pythonResponse->successful()) {
            $pythonData = $pythonResponse->json();
            $pythonLearnMeta = [
                'retrain_scheduled' => (bool) ($pythonData['retrain_scheduled'] ?? false),
                'retrain_in_progress' => (bool) ($pythonData['retrain_in_progress'] ?? false),
                'retrain_started_at' => $pythonData['retrain_started_at'] ?? null,
                'retrain_last_finished_at' => $pythonData['retrain_last_finished_at'] ?? null,
                'retrain_last_status' => $pythonData['retrain_last_status'] ?? null,
                'retrain_last_error' => $pythonData['retrain_last_error'] ?? null,
            ];
        }
    } catch (\Exception $e) {
        // Якщо Python-сервіс недоступний, ми просто ігноруємо помилку, щоб сайт не "впав"
    }

    return response()->json([
        'status' => 'success',
        ...$pythonLearnMeta,
    ]);
})->middleware(['auth']);

// Стандартні маршрути аутентифікації (Login, Register тощо)
require __DIR__.'/auth.php';
