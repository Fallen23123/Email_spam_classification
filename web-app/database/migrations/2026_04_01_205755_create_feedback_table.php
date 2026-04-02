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
        Schema::create('feedback', function (Blueprint $table) {
            $table->id();
            // Хто перевіряв (зв'язок з таблицею користувачів)
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            
            // Сам текст листа, який ми аналізували
            $table->text('email_text');
            
            // Оцінка від Python (ймовірність спаму від 0 до 1)
            $table->float('ai_score');
            
            // Що передбачив ШІ (true - спам, false - ні)
            $table->boolean('is_spam_prediction');
            
            // Чи погодився користувач (натиснув "Вгадала" чи "Помилка")
            $table->boolean('is_user_agrees');
            
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('feedback');
    }
};
