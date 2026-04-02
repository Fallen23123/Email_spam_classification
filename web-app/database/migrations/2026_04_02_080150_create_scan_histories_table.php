<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('scan_histories', function (Blueprint $table) {
            $table->id();
            
            // --- ТУТ ДОДАНІ НОВІ РЯДКИ ---
            $table->foreignId('user_id')->constrained()->cascadeOnDelete(); // Прив'язка до користувача
            $table->float('score'); // Відсоток спаму
            $table->boolean('is_spam'); // Спам чи ні
            // -----------------------------

            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('scan_histories');
    }
};