<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Feedback extends Model
{
    // Обов'язково додай цей рядок, щоб дозволити запис у ці колонки:
    protected $fillable = [
        'user_id', 
        'email_text', 
        'ai_score', 
        'is_spam_prediction', 
        'is_user_agrees'
    ];
}
